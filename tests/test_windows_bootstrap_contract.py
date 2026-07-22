import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "bootstrap/install-sensai.ps1"
BOOTSTRAP_MANIFEST = ROOT / "bootstrap/MANIFEST.sha256"


def test_windows_bootstrap_redeems_fragment_without_printing_bearer() -> None:
    script = BOOTSTRAP.read_text(encoding="utf-8")

    assert ".Fragment" in script
    assert "https://black-vector.com/sensai/invite" in script
    assert "Invoke-RestMethod" in script
    assert "SetEnvironmentVariable" in script
    assert '"SENSAI_INVITE_TOKEN"' in script
    assert "access_token" in script
    assert "Write-Output $token" not in script
    assert "Write-Host $token" not in script
    assert "Write-Information $token" not in script
    assert "SENSAI_BOOTSTRAP_CREDENTIAL_FILE" not in script
    assert "$env:SENSAI_INVITE_TOKEN =" not in script
    assert "Remove-Item Env:SENSAI_INVITE_TOKEN" in script
    assert "codex plugin marketplace add grayskripko/sensai-plugin" not in script
    assert "codex plugin add sensai@sensai" not in script


def test_public_bootstrap_manifest_matches_exact_script() -> None:
    manifest_line = BOOTSTRAP_MANIFEST.read_text(encoding="ascii").strip()
    expected_digest, expected_name = manifest_line.split("  ", maxsplit=1)

    assert expected_name == "install-sensai.ps1"
    assert expected_digest == hashlib.sha256(BOOTSTRAP.read_bytes()).hexdigest()


def test_public_readme_has_only_one_link_agent_driven_setup() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    normalized_readme = " ".join(readme.lower().split())

    assert "https://black-vector.com/sensai/invite#" in readme
    assert "bootstrap/install-sensai.ps1" in readme
    assert "SetEnvironmentVariable" not in readme
    assert "<invitation-key>" not in readme
    assert "SENSAI_INVITE_TOKEN" not in readme
    assert "PowerShell" not in readme
    assert "bootstrap/MANIFEST.sha256" in readme
    assert "one-time" in readme.lower()
    assert "cannot be used again" in readme.lower()
    assert "A full application restart is not part of the normal flow" in readme
    assert "the colleague does not type a second setup phrase" in normalized_readme


def test_bootstrap_tells_the_installing_agent_to_continue_in_a_fresh_chat() -> None:
    script = BOOTSTRAP.read_text(encoding="utf-8")

    assert "SENSAI_AGENT_CONTINUATION_BEGIN" in script
    assert "continue the user's original request without asking for another setup message" in script
    assert "create a fresh chat with this exact initial prompt: Continue Sensai setup" in script
    assert "Do not ask the user to type that prompt." in script
    assert "A full Codex restart is not normally needed." in script
    assert "Fully restart Codex" not in script


def test_real_windows_helper_keeps_access_token_out_of_output(tmp_path: Path) -> None:
    powershell = shutil.which("powershell.exe")
    wslpath = shutil.which("wslpath")
    if powershell is None or wslpath is None:
        pytest.skip("Windows PowerShell interop is unavailable")

    def windows_path(path: Path) -> str:
        result = subprocess.run(
            [wslpath, "-w", str(path)],
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout.strip().replace("'", "''")

    fake_token = "fake-access-token-value-abcdefghijklmnopqrstuvwxyz"
    invitation = "https://black-vector.com/sensai/invite#" + "i" * 48
    stored = tmp_path / "stored-token.txt"
    event_log = tmp_path / "events.txt"
    command = (
        f". '{windows_path(BOOTSTRAP)}' -InvitationUrl '{invitation}'; "
        "$env:SENSAI_INVITE_TOKEN = $null; "
        f"$events = '{windows_path(event_log)}'; "
        "$install = { "
        "if ($env:SENSAI_INVITE_TOKEN) { throw 'Bearer leaked into installer environment.' }; "
        '[IO.File]::AppendAllText($events, "install`n") '
        "}; "
        "$redeem = { param($code) "
        'if ([IO.File]::ReadAllText($events) -ne "install`n") { '
        "throw 'Invitation was redeemed before installation.' }; "
        '[IO.File]::AppendAllText($events, "redeem`n"); '
        f"[pscustomobject]@{{ access_token = '{fake_token}' }} "
        "}; "
        "$store = { param($token) "
        "if ($env:SENSAI_INVITE_TOKEN) { throw 'Bearer leaked into bootstrap environment.' }; "
        '[IO.File]::AppendAllText($events, "store`n"); '
        f"[IO.File]::WriteAllText('{windows_path(stored)}', $token) "
        "}; "
        f"Invoke-SensaiBootstrap -Url '{invitation}' -RedeemCode $redeem "
        "-StoreToken $store -InstallPlugin $install"
    )
    completed = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert stored.read_text(encoding="utf-8") == fake_token
    assert event_log.read_text(encoding="utf-8").splitlines() == ["install", "redeem", "store"]
    assert fake_token not in completed.stdout
    assert fake_token not in completed.stderr
    assert completed.stdout.index("Installing Sensai") < completed.stdout.index(
        "Preparing Sensai access"
    )
    assert "Sensai is installed" in completed.stdout
    assert "SENSAI_AGENT_CONTINUATION_BEGIN" in completed.stdout
    assert "Continue Sensai setup" in completed.stdout
    assert "Do not ask the user to type that prompt." in completed.stdout


def test_failed_install_does_not_redeem_invitation(tmp_path: Path) -> None:
    powershell = shutil.which("powershell.exe")
    wslpath = shutil.which("wslpath")
    if powershell is None or wslpath is None:
        pytest.skip("Windows PowerShell interop is unavailable")

    bootstrap = (
        subprocess.run(
            [wslpath, "-w", str(BOOTSTRAP)],
            text=True,
            capture_output=True,
            check=True,
        )
        .stdout.strip()
        .replace("'", "''")
    )
    redeemed = tmp_path / "redeemed.txt"
    redeemed_windows = (
        subprocess.run(
            [wslpath, "-w", str(redeemed)],
            text=True,
            capture_output=True,
            check=True,
        )
        .stdout.strip()
        .replace("'", "''")
    )
    invitation = "https://black-vector.com/sensai/invite#" + "i" * 48
    command = (
        f". '{bootstrap}' -InvitationUrl '{invitation}'; "
        f"$redeem = {{ param($code) [IO.File]::WriteAllText('{redeemed_windows}', 'yes') }}; "
        "$install = { throw 'Installation failed.' }; "
        "$store = { param($token) throw 'Token must not exist.' }; "
        f"Invoke-SensaiBootstrap -Url '{invitation}' -RedeemCode $redeem "
        "-StoreToken $store -InstallPlugin $install"
    )
    completed = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode != 0
    assert not redeemed.exists()
    assert "same invitation" in completed.stderr.lower()
