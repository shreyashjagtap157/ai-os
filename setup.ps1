# PowerShell setup script for AI-OS prototype (no-op safe)
Write-Host "[AI-OS] Setting up prototype directories and permissions..."
try {
	Get-ChildItem -Path "userland" -Filter *.sh -ErrorAction Stop | ForEach-Object { $_.Attributes = $_.Attributes -bor 'Archive' }
} catch {
	Write-Host "[AI-OS] No shell scripts to adjust."
}
Write-Host "[AI-OS] Done."
