import requests
import json
from django.conf import settings
from urllib.parse import urlencode

# Microsoft Graph API Endpoints
AUTHORITY = "https://login.microsoftonline.com/common"
AUTHORIZE_ENDPOINT = f"{AUTHORITY}/oauth2/v2.0/authorize"
TOKEN_ENDPOINT = f"{AUTHORITY}/oauth2/v2.0/token"
GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0"

SCOPES = ["openid", "offline_access", "Calendars.ReadWrite"]

class OutlookClient:
    """Client สำหรับจัดการการเชื่อมต่อกับ Microsoft Graph API (Outlook Calendar)"""

    def __init__(self, request_uri):
        self.client_id = settings.AZURE_CLIENT_ID
        self.client_secret = settings.AZURE_CLIENT_SECRET
        self.redirect_uri = request_uri
        self.scopes = " ".join(SCOPES)

    def get_auth_url(self):
        """สร้าง URL สำหรับการเริ่มต้น OAuth 2.0 Authorization Code Flow"""
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'response_mode': 'query',
            'scope': self.scopes,
            'state': '12345' 
        }
        return f"{AUTHORIZE_ENDPOINT}?{urlencode(params)}"

    def get_token_from_code(self, authorization_code):
        """แลกเปลี่ยน Authorization Code ที่ได้รับจาก Microsoft เป็น Access Token และ Refresh Token"""
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': authorization_code,
            'redirect_uri': self.redirect_uri,
            'scope': self.scopes
        }
        response = requests.post(TOKEN_ENDPOINT, data=payload)
        response.raise_for_status() 
        return response.json()

    def refresh_token(self, refresh_token):
        """ใช้ Refresh Token เพื่อขอ Access Token ใหม่ เมื่อ Access Token เดิมหมดอายุ"""
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'scope': self.scopes
        }
        response = requests.post(TOKEN_ENDPOINT, data=payload)
        response.raise_for_status()
        return response.json()

    def _get_headers(self, access_token):
        """สร้าง Header สำหรับ API Call"""
        return {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

    def _build_event_payload(self, booking):
        """สร้าง Payload ข้อมูล Event สำหรับ Microsoft Graph"""
        return {
            "subject": f"จองห้อง: {booking.room.name} - {booking.title}",
            "body": {
                "contentType": "HTML",
                "content": f"วัตถุประสงค์: {booking.title}<br>ผู้จอง: {booking.user.get_full_name() or booking.user.username}<br>ห้อง: {booking.room.name}<br>จำนวนคน: {booking.participant_count} คน<br>สถานะ: {booking.get_status_display()}"
            },
            "start": {
                "dateTime": booking.start_time.isoformat(), 
                "timeZone": settings.TIME_ZONE
            },
            "end": {
                "dateTime": booking.end_time.isoformat(),
                "timeZone": settings.TIME_ZONE
            },
            "location": {
                "displayName": f"{booking.room.name}, {booking.room.location}"
            },
            "attendees": [
                {"emailAddress": {"address": user.email, "name": user.get_full_name()}, "type": "required"}
                for user in booking.participants.all()
                if user.email
            ]
        }

    def create_calendar_event(self, access_token, booking):
        """สร้าง Event ในปฏิทิน Outlook ของผู้ใช้"""
        headers = self._get_headers(access_token)
        event_data = self._build_event_payload(booking)
        
        response = requests.post(
            f"{GRAPH_ENDPOINT}/me/events", 
            headers=headers, 
            data=json.dumps(event_data)
        )
        response.raise_for_status()
        return response.json()

    def update_calendar_event(self, access_token, outlook_event_id, booking):
        """อัปเดต Event ในปฏิทิน Outlook"""
        headers = self._get_headers(access_token)
        event_data = self._build_event_payload(booking) 
        
        response = requests.patch(
            f"{GRAPH_ENDPOINT}/me/events/{outlook_event_id}",
            headers=headers,
            data=json.dumps(event_data)
        )
        response.raise_for_status()
        return response.json()

    def delete_calendar_event(self, access_token, outlook_event_id):
        """ลบ Event ออกจากปฏิทิน Outlook"""
        headers = self._get_headers(access_token)
        
        response = requests.delete(
            f"{GRAPH_ENDPOINT}/me/events/{outlook_event_id}",
            headers=headers
        )
        if response.status_code == 404:
            return True 
        
        response.raise_for_status()
        return True