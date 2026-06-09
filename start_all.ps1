# start_all.ps1 - Khởi động toàn bộ hệ thống A2A trên Windows
# Chạy: .\start_all.ps1

Write-Host "=== A2A Multi-Agent System ===" -ForegroundColor Cyan

# Kill bất kỳ process nào đang chiếm ports
Write-Host "Clearing ports 10000-10103..." -ForegroundColor Yellow
$ports = @(10000, 10100, 10101, 10102, 10103)
foreach ($port in $ports) {
    $pid = (netstat -aon | Select-String ":$port " | Select-String "LISTENING" | ForEach-Object { ($_ -split '\s+')[-1] } | Select-Object -First 1)
    if ($pid) {
        taskkill /F /PID $pid 2>$null | Out-Null
        Write-Host "  Killed PID $pid on port $port" -ForegroundColor Gray
    }
}
Start-Sleep -Seconds 1

Write-Host ""
Write-Host "Starting services..." -ForegroundColor Green

# Start Registry
Write-Host "  [1/5] Registry    :10000" -ForegroundColor White
Start-Process -NoNewWindow -FilePath "uv" -ArgumentList "run python -m registry" -PassThru | Out-Null
Start-Sleep -Seconds 2

# Start leaf agents (order doesn't matter)
Write-Host "  [2/5] Tax Agent   :10102" -ForegroundColor White
Start-Process -NoNewWindow -FilePath "uv" -ArgumentList "run python -m tax_agent" -PassThru | Out-Null

Write-Host "  [3/5] Compliance  :10103" -ForegroundColor White
Start-Process -NoNewWindow -FilePath "uv" -ArgumentList "run python -m compliance_agent" -PassThru | Out-Null
Start-Sleep -Seconds 3

# Law agent needs tax+compliance first
Write-Host "  [4/5] Law Agent   :10101" -ForegroundColor White
Start-Process -NoNewWindow -FilePath "uv" -ArgumentList "run python -m law_agent" -PassThru | Out-Null
Start-Sleep -Seconds 3

# Customer agent last
Write-Host "  [5/5] Customer    :10100" -ForegroundColor White
Start-Process -NoNewWindow -FilePath "uv" -ArgumentList "run python -m customer_agent" -PassThru | Out-Null
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "All services started!" -ForegroundColor Green
Write-Host ""
Write-Host "Run test:" -ForegroundColor Cyan
Write-Host "  uv run python test_client_latency.py" -ForegroundColor White
Write-Host ""
Write-Host "To stop all: taskkill /F /IM python.exe" -ForegroundColor Yellow
