[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InvitationUrl
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Invoke-SensaiBootstrap {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [scriptblock]$RedeemCode,
        [scriptblock]$StoreToken,
        [scriptblock]$InstallPlugin
    )

    $parsed = [Uri]$Url
    if (
        $parsed.Scheme -ne "https" -or
        $parsed.Host -ne "black-vector.com" -or
        $parsed.AbsolutePath -ne "/sensai/invite" -or
        -not [string]::IsNullOrEmpty($parsed.Query) -or
        [string]::IsNullOrWhiteSpace($parsed.Fragment)
    ) {
        throw "The Sensai invitation link is invalid."
    }

    $code = $parsed.Fragment.Substring(1)
    if ($code -notmatch '^[A-Za-z0-9_-]{32,128}$') {
        throw "The Sensai invitation link is invalid."
    }

    if ($null -eq $RedeemCode) {
        $RedeemCode = {
            param([string]$OneTimeCode)
            $body = @{ code = $OneTimeCode } | ConvertTo-Json -Compress
            Invoke-RestMethod `
                -Method Post `
                -Uri "https://black-vector.com/sensai/invite" `
                -ContentType "application/json" `
                -Body $body
        }
    }
    if ($null -eq $StoreToken) {
        $StoreToken = {
            param([string]$AccessToken)
            [Environment]::SetEnvironmentVariable(
                "SENSAI_INVITE_TOKEN",
                $AccessToken,
                [EnvironmentVariableTarget]::User
            )
        }
    }
    if ($null -eq $InstallPlugin) {
        $InstallPlugin = {
            Remove-Item Env:SENSAI_INVITE_TOKEN -ErrorAction SilentlyContinue
            $codex = Get-Command codex -ErrorAction Stop
            $null = & $codex.Source plugin marketplace add grayskripko/sensai-plugin --json 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw "Sensai marketplace installation failed."
            }
            $null = & $codex.Source plugin add sensai@sensai --json 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw "Sensai plugin installation failed."
            }
        }
    }

    Write-Host "Installing Sensai..."
    try {
        $null = & $InstallPlugin
    }
    catch {
        throw "Sensai installation did not finish. The same invitation can be used again."
    }

    Write-Host "Preparing Sensai access..."
    try {
        $response = & $RedeemCode $code
    }
    catch {
        throw "Sensai access could not be prepared. Ask for a new invitation."
    }
    $token = $response.access_token
    if ($token -isnot [string] -or $token -notmatch '^[A-Za-z0-9_-]{32,128}$') {
        throw "Sensai access could not be prepared."
    }

    try {
        $null = & $StoreToken $token
    }
    catch {
        throw "Sensai access could not be saved. Ask for a new invitation."
    }
    $token = $null
    $response = $null
    $code = $null

    Write-Host "Sensai is installed. Fully restart Codex, then start a new chat."
}

if ($MyInvocation.InvocationName -ne ".") {
    try {
        Invoke-SensaiBootstrap -Url $InvitationUrl
    }
    catch {
        Write-Error $_.Exception.Message
        exit 1
    }
}
