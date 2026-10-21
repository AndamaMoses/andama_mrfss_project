param(
    [string]$Base = "http://127.0.0.1:5000",
    [ValidateSet("auto", "core", "pro", "growth", "legacy", "tender", "unseeded")]
    [string]$Plan = "auto",
    [string]$Username = "admin",
    [string]$Password = $env:SMOKE_PASSWORD
)

if (-not $Password) { $Password = "admin123" }

$fail = $false
$session = $null
$apps = $null
$detectedPlan = ""
$expectedPlan = ""

function Check([string]$Name, [scriptblock]$Test) {
    try {
        $result = & $Test
        if ($result) { Write-Host "[OK]   $Name" }
        else { Write-Host "[FAIL] $Name"; $script:fail = $true }
    }
    catch {
        Write-Host "[FAIL] $Name - $($_.Exception.Message)"
        $script:fail = $true
    }
}

function Test-Status401([scriptblock]$Request) {
    try {
        & $Request | Out-Null
        return $false
    }
    catch {
        $resp = $_.Exception.Response
        return ($null -ne $resp) -and ([int]$resp.StatusCode -eq 401)
    }
}

function Test-ApiStatus([string]$Path, [int]$Expected) {
    try {
        $r = Invoke-WebRequest "$script:Base$Path" -UseBasicParsing -TimeoutSec 5 -WebSession $script:session
        return ($r.StatusCode -eq $Expected)
    }
    catch {
        $resp = $_.Exception.Response
        return ($null -ne $resp) -and ([int]$resp.StatusCode -eq $Expected)
    }
}

function Get-NoRedirect([string]$Url) {
    $request = [System.Net.HttpWebRequest]::Create($Url)
    $request.AllowAutoRedirect = $false
    $request.Method = "GET"
    $request.Timeout = 5000
    try {
        $response = $request.GetResponse()
    }
    catch [System.Net.WebException] {
        if ($_.Exception.Response) { $response = $_.Exception.Response }
        else { throw }
    }
    try {
        return [pscustomobject]@{
            Status = [int]$response.StatusCode
            Location = [string]$response.Headers["Location"]
        }
    }
    finally {
        $response.Close()
    }
}

function App-Entitled([string]$Id) {
    if (-not $script:apps -or -not $script:apps.apps) { return $false }
    $row = @($script:apps.apps) | Where-Object { $_.id -eq $Id } | Select-Object -First 1
    return [bool]($row -and $row.entitled)
}

Check "GET /api/me (anonymous) -> 200, user null" {
    $r = Invoke-WebRequest "$Base/api/me" -UseBasicParsing -TimeoutSec 5
    ($r.StatusCode -eq 200) -and (($r.Content | ConvertFrom-Json).user -eq $null)
}

Check "GET /api/apps (anonymous) -> 401" {
    Test-Status401 { Invoke-WebRequest "$Base/api/apps" -UseBasicParsing -TimeoutSec 5 }
}

Check "GET /api/products (anonymous) -> 401" {
    Test-Status401 { Invoke-WebRequest "$Base/api/products" -UseBasicParsing -TimeoutSec 5 }
}

Check "POST /api/login $Username" {
    $body = @{ username = $Username; password = $Password } | ConvertTo-Json -Compress
    $r = Invoke-WebRequest "$Base/api/login" -Method Post -UseBasicParsing -TimeoutSec 5 `
        -Body $body -ContentType "application/json" -SessionVariable s
    $script:session = $s
    $r.StatusCode -eq 200
}

Check "GET /api/dashboard (logged in)" {
    (Invoke-WebRequest "$Base/api/dashboard" -UseBasicParsing -TimeoutSec 5 -WebSession $session).StatusCode -eq 200
}

Check "GET /api/apps (logged in)" {
    $r = Invoke-WebRequest "$Base/api/apps" -UseBasicParsing -TimeoutSec 5 -WebSession $session
    $script:apps = $r.Content | ConvertFrom-Json
    ($r.StatusCode -eq 200) -and ($null -ne $script:apps.plan) -and ($null -ne $script:apps.apps)
}

Check "GET /api/apps includes support metadata" {
    ($null -ne $script:apps) -and ($null -ne $script:apps.support)
}

$detectedPlan = if ($apps) { [string]$apps.plan.bundle } else { "" }
$expectedPlan = if ($Plan -eq "auto") { $detectedPlan } else { $Plan }

Check "Plan matches '$expectedPlan' (detected '$detectedPlan')" {
    ($detectedPlan -ne "") -and ($detectedPlan -eq $expectedPlan)
}

$productExpected = if (App-Entitled "pos") { 200 } else { 403 }
$patientsExpected = if (App-Entitled "patients") { 200 } else { 403 }

Check "GET /api/products ($detectedPlan expected $productExpected)" {
    Test-ApiStatus "/api/products" $productExpected
}

Check "GET /api/patients ($detectedPlan expected $patientsExpected)" {
    Test-ApiStatus "/api/patients" $patientsExpected
}

Check "GET /tender ($detectedPlan)" {
    if (App-Entitled "tender") {
        $r = Invoke-WebRequest "$Base/tender" -UseBasicParsing -TimeoutSec 5 -WebSession $session
        ($r.StatusCode -eq 200) -and ($r.Content -match "Tender Copilot")
    }
    else {
        $r = Get-NoRedirect "$Base/tender"
        ($r.Status -eq 302) -and ($r.Location -match "upgrade=tender")
    }
}

foreach ($page in @("/", "/login", "/staff")) {
    Check "GET $page" {
        (Invoke-WebRequest "$($Base)$page" -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200
    }
}

Write-Host "Detected plan: $detectedPlan (expected: $expectedPlan)"
if ($fail) { Write-Host "Smoke checks FAILED"; exit 1 }
Write-Host "All smoke checks passed."
exit 0
