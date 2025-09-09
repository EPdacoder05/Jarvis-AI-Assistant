# API Reference - Jarvis AI Assistant

This document describes the REST API endpoints provided by the Jarvis AI Assistant backend.

## Base URL

After deployment, your API will be available at:
```
https://{api-gateway-id}.execute-api.{region}.amazonaws.com/{environment}
```

## Authentication

All endpoints require an API key passed in the `X-API-Key` header:

```http
X-API-Key: your-secret-api-key
```

## Endpoints

### POST /speak

Converts text to speech using Amazon Polly and returns a presigned URL to the audio file.

#### Request

**Headers:**
- `Content-Type: application/json`
- `X-API-Key: {your-api-key}`

**Body:**
```json
{
  "text": "Hello, this is Jarvis speaking!",
  "voice": "Joanna",
  "format": "mp3"
}
```

**Parameters:**
- `text` (string, required): Text to convert to speech (max 3000 characters)
- `voice` (string, optional): Polly voice ID (default: "Joanna")
- `format` (string, optional): Audio format - "mp3", "ogg_vorbis", "pcm" (default: "mp3")

#### Response

**Success (200):**
```json
{
  "success": true,
  "audio_url": "https://s3.amazonaws.com/bucket/tts_20240101_120000_abc123.mp3?...",
  "filename": "tts_20240101_120000_abc123.mp3",
  "voice": "Joanna",
  "format": "mp3",
  "text_length": 32,
  "expires_in": 3600
}
```

**Error (400):**
```json
{
  "error": "Bad Request: text parameter is required"
}
```

**Error (401):**
```json
{
  "error": "Unauthorized: Invalid or missing API key"
}
```

#### Supported Voices

Amazon Polly Neural voices (recommended):
- `Joanna` (US English, Female)
- `Matthew` (US English, Male)
- `Amy` (British English, Female)
- `Brian` (British English, Male)
- `Emma` (US English, Female)
- `Ivy` (US English, Child)

Standard voices:
- `Kendra` (US English, Female)
- `Kimberly` (US English, Female)
- `Salli` (US English, Female)
- `Joey` (US English, Male)
- `Justin` (US English, Child)

### POST /command

Processes natural language commands and triggers Home Assistant actions.

#### Request

**Headers:**
- `Content-Type: application/json`
- `X-API-Key: {your-api-key}`

**Body:**
```json
{
  "command": "turn on the living room lights"
}
```

**Parameters:**
- `command` (string, required): Natural language command

#### Response

**Success (200):**
```json
{
  "command": "turn on the living room lights",
  "intent": "turn_on_light",
  "parameters": {
    "room": "living room",
    "light_name": null
  },
  "result": {
    "success": true,
    "intent": "turn_on_light",
    "parameters": {
      "room": "living room",
      "light_name": null
    },
    "message": "Successfully executed: turn_on_light"
  }
}
```

**Error (400):**
```json
{
  "error": "Bad Request: command parameter is required"
}
```

**Error (401):**
```json
{
  "error": "Unauthorized: Invalid or missing API key"
}
```

## Supported Commands

### Light Control

**Turn On Lights:**
- "turn on the lights"
- "turn on living room lights"
- "switch on the bedroom lamp"
- "turn on the desk light"

**Turn Off Lights:**
- "turn off all lights"
- "turn off kitchen lights"
- "switch off the lamp"

### Temperature Control

**Set Temperature:**
- "set temperature to 72 degrees"
- "change bedroom temperature to 68"
- "set the thermostat to 75"

### Media Control

**Play Media:**
- "play some music"
- "play jazz playlist"
- "start spotify"

**Stop Media:**
- "stop the music"
- "pause media"
- "stop playing"

### Scene Control

**Activate Scenes:**
- "activate movie night scene"
- "set party mode"
- "turn on romantic scene"

### Security Control

**Lock/Unlock Doors:**
- "lock the front door"
- "unlock the back door"
- "lock all doors"

### Status Queries

**Light Status:**
- "check lights status"
- "how many lights are on"
- "light status"

**Temperature Status:**
- "what's the temperature"
- "check thermostat status"
- "temperature status"

**Security Status:**
- "check door status"
- "are the doors locked"
- "security status"

**General Status:**
- "status report"
- "system status"

## Intent Classification

The system classifies commands into the following intents:

| Intent | Description | Parameters |
|--------|-------------|------------|
| `turn_on_light` | Turn on lights | `room`, `light_name` |
| `turn_off_light` | Turn off lights | `room`, `light_name` |
| `set_temperature` | Set thermostat temperature | `temperature`, `room` |
| `get_weather` | Get weather information | `location` |
| `play_media` | Play music/media | `query`, `type` |
| `stop_media` | Stop media playback | - |
| `activate_scene` | Activate HA scene | `scene_name` |
| `lock_door` | Lock doors | `door` |
| `unlock_door` | Unlock doors | `door` |
| `get_light_status` | Get light status | - |
| `get_temperature_status` | Get temperature status | - |
| `get_security_status` | Get security status | - |
| `get_general_status` | Get general status | - |
| `unknown_command` | Unrecognized command | `original_command` |

## Entity ID Mapping

The system maps natural language to Home Assistant entity IDs:

### Lights
- `"living room"` → `light.living_room_lights`
- `"bedroom"` → `light.bedroom_lights`
- `"desk lamp"` → `light.desk_lamp`
- No specific light → `light.all_lights`

### Climate
- `"bedroom"` → `climate.bedroom`
- `"living room"` → `climate.living_room`
- No specific room → `climate.main_thermostat`

### Media Players
- Default → `media_player.spotify`

### Scenes
- `"movie night"` → `scene.movie_night`
- `"party mode"` → `scene.party_mode`

## Error Handling

### Client Errors (4xx)

| Code | Description | Solution |
|------|-------------|----------|
| 400 | Bad Request | Check required parameters |
| 401 | Unauthorized | Verify API key header |
| 403 | Forbidden | Check API key permissions |
| 429 | Too Many Requests | Implement rate limiting |

### Server Errors (5xx)

| Code | Description | Common Causes |
|------|-------------|---------------|
| 500 | Internal Server Error | Lambda function error, AWS service issue |
| 502 | Bad Gateway | API Gateway configuration issue |
| 503 | Service Unavailable | AWS service outage |
| 504 | Gateway Timeout | Lambda function timeout |

## Rate Limits

Default limits (can be customized):
- 1000 requests per minute per API key
- 10,000 requests per day per API key

## Response Times

Typical response times:
- `/speak` endpoint: 2-5 seconds (includes Polly synthesis and S3 upload)
- `/command` endpoint: 1-3 seconds (includes Home Assistant API call)

## CORS Support

Both endpoints support CORS with the following headers:
- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: POST, OPTIONS`
- `Access-Control-Allow-Headers: Content-Type, X-API-Key`

## WebHook Integration

You can integrate with external services using webhooks. Example for Google Assistant:

```bash
curl -X POST "https://your-api-gateway-url/command" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"command": "{{GoogleAssistant.query}}"}'
```

## SDK Examples

### Python

```python
import requests
import json

class JarvisClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {
            'Content-Type': 'application/json',
            'X-API-Key': api_key
        }
    
    def speak(self, text, voice='Joanna', format='mp3'):
        response = requests.post(
            f'{self.base_url}/speak',
            headers=self.headers,
            json={'text': text, 'voice': voice, 'format': format}
        )
        return response.json()
    
    def command(self, command):
        response = requests.post(
            f'{self.base_url}/command',
            headers=self.headers,
            json={'command': command}
        )
        return response.json()

# Usage
client = JarvisClient('https://api123.execute-api.us-east-1.amazonaws.com/dev', 'your-api-key')
result = client.speak('Hello World')
print(result['audio_url'])
```

### JavaScript/Node.js

```javascript
class JarvisClient {
    constructor(baseUrl, apiKey) {
        this.baseUrl = baseUrl;
        this.headers = {
            'Content-Type': 'application/json',
            'X-API-Key': apiKey
        };
    }
    
    async speak(text, voice = 'Joanna', format = 'mp3') {
        const response = await fetch(`${this.baseUrl}/speak`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({ text, voice, format })
        });
        return await response.json();
    }
    
    async command(command) {
        const response = await fetch(`${this.baseUrl}/command`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({ command })
        });
        return await response.json();
    }
}

// Usage
const client = new JarvisClient('https://api123.execute-api.us-east-1.amazonaws.com/dev', 'your-api-key');
const result = await client.speak('Hello World');
console.log(result.audio_url);
```

### cURL Examples

```bash
# Text-to-Speech
curl -X POST "https://your-api-gateway-url/speak" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "text": "Welcome home! All systems are operational.",
    "voice": "Joanna",
    "format": "mp3"
  }'

# Command Processing
curl -X POST "https://your-api-gateway-url/command" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "command": "turn on all the lights and set temperature to 72 degrees"
  }'

# Check status
curl -X POST "https://your-api-gateway-url/command" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "command": "what is the current status"
  }'
```