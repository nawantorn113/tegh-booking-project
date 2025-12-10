Write-Host "🔄 Starting automatic loaddata...`n"

$files = @(
    "group_fixed.json",
    "permission_fixed.json",
    "user_fixed.json",
    "userprofile_fixed.json",
    "room_fixed.json",
    "equipment_fixed.json",
    "booking_fixed.json"
)

foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "➡️  Loading $file ..."
        python manage.py loaddata $file
        Write-Host "`n"
    }
    else {
        Write-Host "⚠️  File not found: $file"
    }
}

Write-Host "🎉 DONE! All fixtures loaded."
