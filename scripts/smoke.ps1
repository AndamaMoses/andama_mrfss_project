param([string]$Base = "http://127.0.0.1:5000")
$fail = $false

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
        return ($null -ne $resp) -and ($resp.StatusCode.value__ -eq 401)
    }
}

$session = $null

Check "GET /api/me (anonymous) -> 200, user null" {
    $r = Invoke-WebRequest "$Base/api/me" -UseBasicParsing -TimeoutSec 5
    ($r.StatusCode -eq 200) -and (($r.Content | ConvertFrom-Json).user -eq $null)
}

Check "GET /api/products (anonymous) -> 401" {
    Test-Status401 { Invoke-WebRequest "$Base/api/products" -UseBasicParsing -TimeoutSec 5 }
}

Check "POST /api/login admin" {
    $r = Invoke-WebRequest "$Base/api/login" -Method Post -UseBasicParsing -TimeoutSec 5 `
        -Body '{"username":"admin","password":"admin123"}' `
        -ContentType "application/json" -SessionVariable s
    $script:session = $s
    $r.StatusCode -eq 200
}

Check "GET /api/dashboard (logged in)" {
    (Invoke-WebRequest "$Base/api/dashboard" -UseBasicParsing -TimeoutSec 5 -WebSession $session).StatusCode -eq 200
}

Check "GET /api/products (logged in)" {
    (Invoke-WebRequest "$Base/api/products" -UseBasicParsing -TimeoutSec 5 -WebSession $session).StatusCode -eq 200
}

foreach ($page in @("/", "/login", "/staff", "/tender")) {
    Check "GET $page" {
        (Invoke-WebRequest "$Base$page" -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200
    }
}

if ($fail) { Write-Host "Smoke checks FAILED"; exit 1 }
Write-Host "All smoke checks passed."
exit 0
