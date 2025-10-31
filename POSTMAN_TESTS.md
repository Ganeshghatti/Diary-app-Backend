# Postman API Test Guide

## Base URL
```
http://localhost:4000
```

---

## 🔐 Authentication Routes

### 1. Request OTP
**Method:** `POST`  
**URL:** `http://localhost:4000/auth/request-otp`  
**Headers:**
```
Content-Type: application/json
```
**Body (JSON):**
```json
{
  "phone": "9876543210"
}
```
**Expected Response:**
```json
{
  "message": "OTP sent successfully"
}
```

---

### 2. Verify OTP (Signup/Login)
**Method:** `POST`  
**URL:** `http://localhost:4000/auth/verify-otp`  
**Headers:**
```
Content-Type: application/json
X-Timezone: Asia/Kolkata
```
**Body (JSON):**
```json
{
  "phone": "9876543210",
  "otp": "123456"
}
```
**Note:** `X-Timezone` header is only used during NEW user signup. For existing users, it's ignored.

**Expected Response:**
```json
{
  "message": "OTP verified successfully.",
  "phone": "9876543210",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "newly_created": false,
  "user": {
    "phone": "9876543210",
    "timezone": "Asia/Kolkata",
    "created_at": "2024-01-15T10:30:00"
  }
}
```
**💡 Save the `token` from response for authenticated requests!**

---

## 👤 User Profile Routes

### 3. Get Profile
**Method:** `GET`  
**URL:** `http://localhost:4000/user/profile`  
**Headers:**
```
Authorization: Bearer YOUR_TOKEN_HERE
```
**Expected Response:**
```json
{
  "user": {
    "phone": "9876543210",
    "name": "John Doe",
    "email": "john@example.com",
    "timezone": "Asia/Kolkata",
    "profile_pic_url": "/uploads/profile_pics/65a1b2c3d4e5f6g7h8i9j0k1.jpg",
    "profile_pic": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD...",
    "created_at": "2024-01-15T10:30:00"
  }
}
```
**Note:** `profile_pic` contains base64-encoded image data that can be used directly in HTML `<img>` tag: `<img src="data:image/jpeg;base64,..." />`

---

### 4. Update Profile (JSON - name, email, timezone only)
**Method:** `PUT`  
**URL:** `http://localhost:4000/user/profile`  
**Headers:**
```
Content-Type: application/json
Authorization: Bearer YOUR_TOKEN_HERE
```
**Body (JSON):**
```json
{
  "name": "John Doe",
  "email": "john.doe@example.com",
  "timezone": "America/New_York"
}
```
**Expected Response:**
```json
{
  "message": "Profile updated successfully.",
  "user": {
    "phone": "9876543210",
    "name": "John Doe",
    "email": "john.doe@example.com",
    "timezone": "America/New_York",
    "profile_pic_url": "/uploads/profile_pics/65a1b2c3d4e5f6g7h8i9j0k1.jpg",
    "profile_pic": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD...",
    "created_at": "2024-01-15T10:30:00"
  }
}
```

---

### 5. Update Profile with Image (multipart/form-data)
**Method:** `PUT`  
**URL:** `http://localhost:4000/user/profile`  
**Headers:**
```
Authorization: Bearer YOUR_TOKEN_HERE
```
**Note:** Don't set Content-Type header manually - Postman will set it automatically with boundary.

**Body (form-data):**
- Key: `name` | Type: Text | Value: `John Doe`
- Key: `email` | Type: Text | Value: `john@example.com`
- Key: `timezone` | Type: Text | Value: `Asia/Kolkata`
- Key: `profile_pic` | Type: File | Value: `[Select Image File]`

**Expected Response:**
```json
{
  "message": "Profile updated successfully.",
  "user": {
    "phone": "9876543210",
    "name": "John Doe",
    "email": "john@example.com",
    "timezone": "Asia/Kolkata",
    "profile_pic_url": "/uploads/profile_pics/65a1b2c3d4e5f6g7h8i9j0k1.jpg",
    "profile_pic": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD...",
    "created_at": "2024-01-15T10:30:00"
  }
}
```
**Note:** `profile_pic` contains base64-encoded image data ready to use in frontend.

---

## 📔 Diary Routes

**Note:** All diary routes require `Authorization: Bearer YOUR_TOKEN_HERE` header.

---

### 6. Create/Update Diary Entry (Upsert)
**Method:** `POST` or `PUT`  
**URL:** `http://localhost:4000/diary`  
**Headers:**
```
Content-Type: application/json
Authorization: Bearer YOUR_TOKEN_HERE
```
**Body (JSON) - Full Example:**
```json
{
  "diary": {
    "content": "Today was a great day! I went for a walk in the morning and had a productive afternoon working on my project.",
    "summary": "Great day with morning walk and productive work"
  },
  "mood_tracker": [
    "happy",
    "energetic",
    "focused",
    "grateful"
  ],
  "expense_tracker": [
    {
      "name": "Lunch",
      "amount": 250.50
    },
    {
      "name": "Coffee",
      "amount": 120.00
    },
    {
      "name": "Groceries",
      "amount": 1500.00
    }
  ],
  "health_stats": [
    {
      "name": "Steps",
      "description": "Daily step count",
      "value": 8500,
      "unit": "steps"
    },
    {
      "name": "Water Intake",
      "description": "Daily water consumption",
      "value": 2.5,
      "unit": "liters"
    },
    {
      "name": "Weight",
      "description": "Body weight measurement",
      "value": 70.5,
      "unit": "kg"
    }
  ]
}
```

**Body (JSON) - Minimal Example (just diary content):**
```json
{
  "diary": {
    "content": "Quick note for today"
  }
}
```

**Body (JSON) - Update Mood Only:**
```json
{
  "mood_tracker": [
    "calm",
    "grateful",
    "peaceful"
  ]
}
```

**Body (JSON) - Update Expenses Only:**
```json
{
  "expense_tracker": [
    {
      "name": "Dinner",
      "amount": 350.00
    },
    {
      "name": "Movie",
      "amount": 500.00
    }
  ]
}
```

**Body (JSON) - Update Health Stats Only:**
```json
{
  "health_stats": [
    {
      "name": "Blood Pressure",
      "description": "Morning reading",
      "value": 120,
      "unit": "mmHg"
    },
    {
      "name": "Heart Rate",
      "description": "Resting heart rate",
      "value": 72,
      "unit": "bpm"
    }
  ]
}
```

**Expected Response (Created):**
```json
{
  "message": "Diary entry created successfully.",
  "date": "15-01-2024",
  "id": "65a1b2c3d4e5f6g7h8i9j0k1"
}
```

**Expected Response (Updated):**
```json
{
  "message": "Diary entry updated successfully.",
  "date": "15-01-2024"
}
```

---

### 7. Get Diary Entry by Date
**Method:** `GET`  
**URL:** `http://localhost:4000/diary?date=15-01-2024`  
**Headers:**
```
Authorization: Bearer YOUR_TOKEN_HERE
```
**Expected Response:**
```json
{
  "diary": {
    "_id": "65a1b2c3d4e5f6g7h8i9j0k1",
    "user_id": "65a1b2c3d4e5f6g7h8i9j0k2",
    "date": "15-01-2024",
    "created_at": "2024-01-15T15:30:00+05:30",
    "last_update": "2024-01-15T18:45:00+05:30",
    "update_log": [
      {
        "timestamp": "2024-01-15T15:30:00+05:30"
      },
      {
        "timestamp": "2024-01-15T18:45:00+05:30"
      }
    ],
    "diary": {
      "content": "Today was a great day!",
      "summary": "Great day with morning walk"
    },
    "mood_tracker": ["happy", "energetic", "focused"],
    "expense_tracker": [
      {
        "name": "Lunch",
        "amount": 250.5
      }
    ],
    "health_stats": [
      {
        "name": "Steps",
        "description": "Daily step count",
        "value": 8500,
        "unit": "steps"
      }
    ]
  }
}
```

---

### 8. Get All Diaries for Current Month
**Method:** `GET`  
**URL:** `http://localhost:4000/diary/month`  
**Headers:**
```
Authorization: Bearer YOUR_TOKEN_HERE
```
**Expected Response:**
```json
{
  "diaries": [
    {
      "_id": "65a1b2c3d4e5f6g7h8i9j0k1",
      "user_id": "65a1b2c3d4e5f6g7h8i9j0k2",
      "date": "15-01-2024",
      "created_at": "2024-01-15T15:30:00+05:30",
      "last_update": "2024-01-15T18:45:00+05:30",
      "diary": {
        "content": "Today was a great day!"
      },
      "mood_tracker": ["happy"]
    }
  ]
}
```

---

### 9. Get All Diaries
**Method:** `GET`  
**URL:** `http://localhost:4000/diary/all`  
**Headers:**
```
Authorization: Bearer YOUR_TOKEN_HERE
```
**Expected Response:**
```json
{
  "diaries": [
    {
      "_id": "65a1b2c3d4e5f6g7h8i9j0k1",
      "user_id": "65a1b2c3d4e5f6g7h8i9j0k2",
      "date": "15-01-2024",
      "created_at": "2024-01-15T15:30:00+05:30",
      "last_update": "2024-01-15T18:45:00+05:30",
      "diary": {
        "content": "Today was a great day!"
      },
      "mood_tracker": ["happy", "energetic"]
    }
  ]
}
```

---

### 10. Delete Diary Entry by Date
**Method:** `DELETE`  
**URL:** `http://localhost:4000/diary?date=15-01-2024`  
**Headers:**
```
Authorization: Bearer YOUR_TOKEN_HERE
```
**Expected Response:**
```json
{
  "message": "Diary entry deleted successfully."
}
```

---

## 🔐 Admin Routes

### Admin Login
**Method:** `POST`  
**URL:** `http://localhost:4000/admin/login`  
**Headers:**
```
Content-Type: application/json
```
**Body (JSON):**
```json
{
  "email": "admin@diarydad.me",
  "password": "adminpass1"
}
```
**Expected Response:**
```json
{
  "message": "Admin login successful",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "email": "admin@diarydad.me"
}
```
**💡 Save the `token` from response for admin requests!**

---

### Get All Users
**Method:** `GET`  
**URL:** `http://localhost:4000/admin/users`  
**Headers:**
```
Authorization: Bearer ADMIN_TOKEN_HERE
```
**Expected Response:**
```json
{
  "users": [
    {
      "_id": "65a1b2c3d4e5f6g7h8i9j0k1",
      "phone": "9876543210",
      "name": "John Doe",
      "email": "john@example.com",
      "timezone": "Asia/Kolkata",
      "created_at": "2024-01-15T10:30:00"
    }
  ],
  "total": 1
}
```

---

### Get User Details
**Method:** `GET`  
**URL:** `http://localhost:4000/admin/users/{user_id}`  
**Headers:**
```
Authorization: Bearer ADMIN_TOKEN_HERE
```
**Example:** `http://localhost:4000/admin/users/65a1b2c3d4e5f6g7h8i9j0k1`

**Expected Response:**
```json
{
  "user": {
    "_id": "65a1b2c3d4e5f6g7h8i9j0k1",
    "phone": "9876543210",
    "name": "John Doe",
    "email": "john@example.com",
    "timezone": "Asia/Kolkata",
    "profile_pic_url": "/uploads/profile_pics/65a1b2c3d4e5f6g7h8i9j0k1.jpg",
    "created_at": "2024-01-15T10:30:00",
    "total_diary_entries": 15,
    "last_diary_entry": "2024-01-20T18:45:00",
    "today_image_extractions": 1,
    "today_summary_generations": 2
  }
}
```

---

### Get Engagement Statistics
**Method:** `GET`  
**URL:** `http://localhost:4000/admin/engagement`  
**Headers:**
```
Authorization: Bearer ADMIN_TOKEN_HERE
```
**Expected Response:**
```json
{
  "summary": {
    "total_users": 100,
    "today": {
      "active_users": 25,
      "engagement_rate": 25.0
    },
    "this_week": {
      "active_users": 60,
      "engagement_rate": 60.0
    },
    "this_month": {
      "active_users": 80,
      "engagement_rate": 80.0
    },
    "last_7_days": {
      "active_users": 65,
      "engagement_rate": 65.0
    },
    "last_30_days": {
      "active_users": 85,
      "engagement_rate": 85.0
    },
    "last_90_days": {
      "active_users": 95,
      "engagement_rate": 95.0
    }
  },
  "graphs": {
    "daily": [
      {
        "date": "2024-01-01",
        "active_users": 20,
        "total_users": 100,
        "engagement_rate": 20.0
      },
      {
        "date": "2024-01-02",
        "active_users": 25,
        "total_users": 100,
        "engagement_rate": 25.0
      }
    ],
    "weekly": [
      {
        "week_start": "2024-01-01",
        "week_end": "2024-01-07",
        "active_users": 60,
        "total_users": 100,
        "engagement_rate": 60.0
      }
    ],
    "monthly": [
      {
        "month": "2024-01",
        "month_name": "January 2024",
        "active_users": 80,
        "total_users": 100,
        "engagement_rate": 80.0
      }
    ]
  }
}
```

**Graph Data Usage:**
- **daily**: Last 30 days - use for line/bar chart showing daily engagement
- **weekly**: Last 12 weeks - use for weekly trend analysis
- **monthly**: Last 12 months - use for long-term trend analysis

---

## 📋 Testing Sequence

1. **Request OTP** → Get OTP (check SMS or console logs)
2. **Verify OTP** → Get token (save it)
3. **Get Profile** → View current profile
4. **Update Profile** → Add name, email, upload profile pic
5. **Get Profile** → Verify updates
6. **Create Diary** → POST with full data
7. **Get Diary** → GET by date (use today's date in your timezone)
8. **Update Diary** → PUT with partial data
9. **Get Month Diaries** → View current month entries
10. **Get All Diaries** → View all entries
11. **Delete Diary** → DELETE by date

---

## 🖼️ Profile Picture Usage

Profile pictures are returned as **base64-encoded data URIs** in the `profile_pic` field. 

**Frontend Usage:**
```html
<!-- Direct use in img tag -->
<img src="{{user.profile_pic}}" alt="Profile Picture" />

<!-- React/React Native -->
<Image source={{ uri: user.profile_pic }} />

<!-- JavaScript -->
document.getElementById('profile-img').src = user.profile_pic;
```

The image is also accessible via direct URL (if needed):
```
http://localhost:4000/uploads/profile_pics/{user_id}.jpg
```

---

## 🤖 AI Features (3 uses per day limit)

### 11. Extract Text from Image
**Method:** `POST`  
**URL:** `http://localhost:4000/diary/extract-text`  
**Headers:**
```
Authorization: Bearer YOUR_TOKEN_HERE
```
**Body (form-data):**
- Key: `image` | Type: File | Value: `[Select Image File]`

**Expected Response:**
```json
{
  "text": "Today I went for a walk in the park. The weather was beautiful...",
  "image_url": "/uploads/diary_images/65a1b2c3d4e5f6g7h8i9j0k1_20240115_143025.jpg",
  "remaining_uses": 2
}
```

**Note:** 
- Saves image to server with filename: `{user_id}_{timestamp}.{extension}`
- Max 3 extractions per day (per diary entry/day)
- Returns extracted text and image URL

---

### 12. Generate Summary (Streaming)
**Method:** `POST`  
**URL:** `http://localhost:4000/diary/generate-summary`  
**Headers:**
```
Content-Type: application/json
Authorization: Bearer YOUR_TOKEN_HERE
```
**Body (JSON):**
```json
{
  "text": "Today was a wonderful day. I woke up early and went for a morning jog. After that, I had breakfast with my family and we spent time together. In the afternoon, I worked on my project and made great progress. In the evening, I met some friends for dinner and we had a great conversation about life and our goals."
}
```

**Expected Response (Server-Sent Events - SSE):**
```
data: {"type": "start", "remaining_uses": 2}

data: {"type": "chunk", "text": "Today"}

data: {"type": "chunk", "text": " was"}

data: {"type": "chunk", "text": " a"}

data: {"type": "chunk", "text": " productive"}

data: {"type": "chunk", "text": " day"}

...

data: {"type": "complete"}
```

**Frontend Usage (JavaScript):**
```javascript
const eventSource = new EventSource('/diary/generate-summary', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});

// Note: EventSource doesn't support POST with body, use fetch instead:
fetch('/diary/generate-summary', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({ text: diaryText })
}).then(response => {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  
  function readStream() {
    reader.read().then(({ done, value }) => {
      if (done) return;
      const chunk = decoder.decode(value);
      const lines = chunk.split('\n\n');
      lines.forEach(line => {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.substring(6));
          if (data.type === 'chunk') {
            console.log('Text chunk:', data.text);
          } else if (data.type === 'complete') {
            console.log('Stream complete');
          }
        }
      });
      readStream();
    });
  }
  readStream();
});
```

**Note:**
- Max 3 summaries per day (per diary entry/day)
- Streams response in real-time using Server-Sent Events (SSE)
- Requires `GEMINI_API_KEY` environment variable

---

## ⚠️ Common Errors

**401 Unauthorized:**
```json
{
  "error": "Authorization header missing or invalid"
}
```
Solution: Add `Authorization: Bearer YOUR_TOKEN` header

**400 Bad Request:**
```json
{
  "error": "Date must be in DD-MM-YYYY format."
}
```
Solution: Use correct date format: `15-01-2024`

**404 Not Found:**
```json
{
  "error": "No diary found for this date."
}
```
Solution: Create diary entry first or check date format

**429 Too Many Requests:**
```json
{
  "error": "Daily limit reached. You can extract text from images only 3 times per day."
}
```
or
```json
{
  "error": "Daily limit reached. You can generate summaries only 3 times per day."
}
```
Solution: Wait until next day or use remaining daily quota

---

## 📝 Notes

- **Date Format:** Always use `DD-MM-YYYY` format (e.g., `15-01-2024`)
- **Timezone:** User timezone affects date queries - date is converted to UTC range for database queries
- **Token:** No expiration - tokens are valid indefinitely
- **Profile Pic:** Stored as `{user_id}.jpg` in `uploads/profile_pics/`, returned as base64 data URI
- **Mood Tracker:** Maximum 5 items allowed
- **Diary Date:** Frontend doesn't send date - backend always uses current UTC date
- **Usage Tracking:** Image extraction and summary generation usage tracked per day in diary model (3 uses/day each)
- **Diary Images:** Saved as `{user_id}_{timestamp}.{extension}` in `uploads/diary_images/`
- **Gemini API:** Requires `GEMINI_API_KEY` environment variable for summary generation

