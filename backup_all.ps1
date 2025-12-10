param(
    [string]$BackupDir = "backups"
)

# 1. Create backup folder if not exists
if (!(Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

# 2. Date tag for filenames
$DATE = Get-Date -Format "yyyyMMdd_HHmmss"

Write-Host "Starting Django Backup ($DATE)..." -ForegroundColor Cyan

# 3. Helper function
function Dump-Data {
    param($Label, $ModelName)

    $FileName = "$BackupDir/${Label}_$DATE.json"

    Write-Host "-> Exporting $Label ..." -ForegroundColor Yellow

    # FIX 1: ใช้ -X utf8 เพื่อบังคับ Python ให้รองรับภาษาไทย
    # FIX 2: ใช้ --output ของ Django เพื่อเขียนไฟล์โดยตรง (เลี่ยงปัญหา PowerShell Redirect)
    python -X utf8 manage.py dumpdata $ModelName --indent 2 --output $FileName

    if ($LASTEXITCODE -eq 0) {
        Write-Host "   [OK] Saved: $FileName" -ForegroundColor Green
    } else {
        Write-Host "   [ERROR] Exporting $Label" -ForegroundColor Red
    }
}

# 4. Dump models (แก้ไขชื่อตารางให้ถูกต้องแล้ว)
Dump-Data "user"                 "auth.User"
Dump-Data "group"                "auth.Group"
Dump-Data "permission"           "auth.Permission"
Dump-Data "contenttype"          "contenttypes.ContentType"
Dump-Data "userprofile"          "booking.UserProfile"
Dump-Data "room"                 "booking.Room"
Dump-Data "equipment"            "booking.Equipment"
Dump-Data "booking"              "booking.Booking"

# FIX 3: แก้ชื่อตาราง Many-to-Many เป็นชื่อ Model จริงๆ ที่ Django สร้างให้
Dump-Data "booking_participants" "booking.Booking_participants"

Write-Host "Backup Completed!" -ForegroundColor Cyan