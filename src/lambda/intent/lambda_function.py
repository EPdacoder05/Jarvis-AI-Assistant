import json
import boto3
import requests
import os
import logging
import re
from typing import Dict, Any, Tuple

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
secrets_client = boto3.client('secretsmanager')

# Environment variables
API_KEY = os.environ.get('API_KEY')
HA_SECRET_NAME = os.environ.get('HA_SECRET_NAME', 'jarvis/homeassistant')

# Cache for Home Assistant credentials
_ha_credentials = None

def get_ha_credentials():
    """Get Home Assistant credentials from Secrets Manager"""
    global _ha_credentials
    
    if _ha_credentials is None:
        try:
            response = secrets_client.get_secret_value(SecretId=HA_SECRET_NAME)
            secret = json.loads(response['SecretString'])
            _ha_credentials = {
                'url': secret['url'],
                'token': secret['token']
            }
            logger.info("Successfully retrieved HA credentials from Secrets Manager")
        except Exception as e:
            logger.error(f"Failed to retrieve HA credentials: {str(e)}")
            raise
    
    return _ha_credentials

def parse_command(command: str) -> Tuple[str, Dict[str, Any]]:
    """
    Parse natural language command and extract intent and parameters
    
    Returns:
        Tuple of (intent, parameters)
    """
    command = command.lower().strip()
    
    # Light control patterns
    if re.search(r'\b(turn on|switch on|on)\b.*\b(light|lights|lamp|lamps)\b', command):
        # Extract room/location if mentioned
        room_match = re.search(r'\b(bedroom|living room|kitchen|bathroom|office|dining room|garage|basement)\b', command)
        room = room_match.group(1) if room_match else None
        
        # Extract specific light name
        light_match = re.search(r'\b(turn on|switch on|on)\s+(?:the\s+)?([a-zA-Z\s]+?)\s+(?:light|lamp)', command)
        light_name = light_match.group(2).strip() if light_match else None
        
        return 'turn_on_light', {'room': room, 'light_name': light_name}
    
    elif re.search(r'\b(turn off|switch off|off)\b.*\b(light|lights|lamp|lamps)\b', command):
        room_match = re.search(r'\b(bedroom|living room|kitchen|bathroom|office|dining room|garage|basement)\b', command)
        room = room_match.group(1) if room_match else None
        
        light_match = re.search(r'\b(turn off|switch off|off)\s+(?:the\s+)?([a-zA-Z\s]+?)\s+(?:light|lamp)', command)
        light_name = light_match.group(2).strip() if light_match else None
        
        return 'turn_off_light', {'room': room, 'light_name': light_name}
    
    # Temperature control
    elif re.search(r'\b(set|change)\b.*\btemperature\b', command):
        temp_match = re.search(r'\b(\d+)\s*(?:degrees?|°)?\b', command)
        temperature = int(temp_match.group(1)) if temp_match else None
        
        room_match = re.search(r'\b(bedroom|living room|kitchen|bathroom|office|dining room)\b', command)
        room = room_match.group(1) if room_match else None
        
        return 'set_temperature', {'temperature': temperature, 'room': room}
    
    # Weather query
    elif re.search(r'\b(weather|temperature|forecast)\b', command):
        location_match = re.search(r'\bin\s+([a-zA-Z\s]+)', command)
        location = location_match.group(1).strip() if location_match else None
        
        return 'get_weather', {'location': location}
    
    # Media control
    elif re.search(r'\b(play|start|resume)\b.*\b(music|song|playlist|spotify|youtube)\b', command):
        query_match = re.search(r'\bplay\s+([^,\.]+)', command)
        query = query_match.group(1).strip() if query_match else None
        
        return 'play_media', {'query': query, 'type': 'music'}
    
    elif re.search(r'\b(stop|pause|halt)\b.*\b(music|song|media|playing)\b', command):
        return 'stop_media', {}
    
    # Scene control
    elif re.search(r'\b(activate|set|turn on)\b.*\bscene\b', command):
        scene_match = re.search(r'\bscene\s+([a-zA-Z\s]+)', command)
        scene_name = scene_match.group(1).strip() if scene_match else None
        
        return 'activate_scene', {'scene_name': scene_name}
    
    # Door/lock control
    elif re.search(r'\b(lock|unlock)\b.*\b(door|doors)\b', command):
        action = 'lock' if 'lock' in command else 'unlock'
        door_match = re.search(r'\b(front|back|side|garage)\s+door\b', command)
        door = door_match.group(0) if door_match else 'front door'
        
        return f'{action}_door', {'door': door}
    
    # Status queries
    elif re.search(r'\b(status|state|check)\b', command):
        if 'lights' in command:
            return 'get_light_status', {}
        elif 'temperature' in command:
            return 'get_temperature_status', {}
        elif 'doors' in command or 'locks' in command:
            return 'get_security_status', {}
        else:
            return 'get_general_status', {}
    
    # Default fallback
    else:
        return 'unknown_command', {'original_command': command}

def execute_ha_command(intent: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute command on Home Assistant"""
    
    credentials = get_ha_credentials()
    base_url = credentials['url'].rstrip('/')
    headers = {
        'Authorization': f"Bearer {credentials['token']}",
        'Content-Type': 'application/json'
    }
    
    try:
        if intent == 'turn_on_light':
            entity_id = build_light_entity_id(parameters.get('light_name'), parameters.get('room'))
            url = f"{base_url}/api/services/light/turn_on"
            data = {'entity_id': entity_id}
            
        elif intent == 'turn_off_light':
            entity_id = build_light_entity_id(parameters.get('light_name'), parameters.get('room'))
            url = f"{base_url}/api/services/light/turn_off"
            data = {'entity_id': entity_id}
            
        elif intent == 'set_temperature':
            entity_id = build_climate_entity_id(parameters.get('room'))
            url = f"{base_url}/api/services/climate/set_temperature"
            data = {
                'entity_id': entity_id,
                'temperature': parameters.get('temperature', 70)
            }
            
        elif intent == 'play_media':
            url = f"{base_url}/api/services/media_player/play_media"
            data = {
                'entity_id': 'media_player.spotify',  # Default media player
                'media_content_id': parameters.get('query', ''),
                'media_content_type': 'music'
            }
            
        elif intent == 'stop_media':
            url = f"{base_url}/api/services/media_player/media_stop"
            data = {'entity_id': 'media_player.spotify'}
            
        elif intent == 'activate_scene':
            scene_entity = f"scene.{parameters.get('scene_name', '').replace(' ', '_').lower()}"
            url = f"{base_url}/api/services/scene/turn_on"
            data = {'entity_id': scene_entity}
            
        elif intent in ['get_light_status', 'get_temperature_status', 'get_security_status', 'get_general_status']:
            # For status queries, get states instead of calling services
            url = f"{base_url}/api/states"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                states = response.json()
                return format_status_response(intent, states, parameters)
            else:
                return {'success': False, 'error': f'Failed to get status: {response.status_code}'}
        
        else:
            return {
                'success': False,
                'error': f'Unknown intent: {intent}',
                'suggestion': 'Try commands like "turn on lights", "set temperature to 72", or "play music"'
            }
        
        # Execute the service call
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code in [200, 201]:
            return {
                'success': True,
                'intent': intent,
                'parameters': parameters,
                'message': f'Successfully executed: {intent}'
            }
        else:
            return {
                'success': False,
                'error': f'Home Assistant error: {response.status_code}',
                'details': response.text
            }
            
    except requests.exceptions.Timeout:
        return {'success': False, 'error': 'Home Assistant request timeout'}
    except requests.exceptions.ConnectionError:
        return {'success': False, 'error': 'Cannot connect to Home Assistant'}
    except Exception as e:
        return {'success': False, 'error': f'Unexpected error: {str(e)}'}

def build_light_entity_id(light_name: str, room: str) -> str:
    """Build entity ID for light based on name and room"""
    if light_name:
        return f"light.{light_name.replace(' ', '_').lower()}"
    elif room:
        return f"light.{room.replace(' ', '_').lower()}_lights"
    else:
        return "light.all_lights"  # Default to all lights

def build_climate_entity_id(room: str) -> str:
    """Build entity ID for climate control"""
    if room:
        return f"climate.{room.replace(' ', '_').lower()}"
    else:
        return "climate.main_thermostat"

def format_status_response(intent: str, states: list, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Format status response based on intent"""
    
    if intent == 'get_light_status':
        lights = [s for s in states if s['entity_id'].startswith('light.')]
        on_lights = [l for l in lights if l['state'] == 'on']
        
        return {
            'success': True,
            'intent': intent,
            'data': {
                'total_lights': len(lights),
                'lights_on': len(on_lights),
                'on_lights': [l['entity_id'] for l in on_lights]
            },
            'message': f'{len(on_lights)} out of {len(lights)} lights are currently on'
        }
    
    elif intent == 'get_temperature_status':
        climate = [s for s in states if s['entity_id'].startswith('climate.')]
        temp_data = []
        
        for c in climate:
            temp_data.append({
                'entity': c['entity_id'],
                'current_temp': c['attributes'].get('current_temperature'),
                'target_temp': c['attributes'].get('temperature'),
                'state': c['state']
            })
        
        return {
            'success': True,
            'intent': intent,
            'data': {'climate_entities': temp_data},
            'message': f'Retrieved status for {len(temp_data)} climate entities'
        }
    
    # Add more status formatters as needed
    return {
        'success': True,
        'intent': intent,
        'data': {'total_entities': len(states)},
        'message': f'Retrieved general status for {len(states)} entities'
    }

def lambda_handler(event, context):
    """
    Intent Lambda function - processes voice commands and triggers Home Assistant actions
    """
    try:
        # Parse the incoming request
        if 'body' in event:
            body = json.loads(event['body'])
        else:
            body = event
        
        # Validate API key
        headers = event.get('headers', {})
        provided_key = headers.get('x-api-key') or headers.get('X-API-Key')
        
        if not provided_key or provided_key != API_KEY:
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Unauthorized: Invalid or missing API key'
                })
            }
        
        # Extract command from request
        command = body.get('command', '').strip()
        
        if not command:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Bad Request: command parameter is required'
                })
            }
        
        logger.info(f"Processing command: {command}")
        
        # Parse the command to extract intent and parameters
        intent, parameters = parse_command(command)
        
        logger.info(f"Parsed intent: {intent}, parameters: {parameters}")
        
        # Execute the command on Home Assistant
        result = execute_ha_command(intent, parameters)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'command': command,
                'intent': intent,
                'parameters': parameters,
                'result': result
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing command: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal Server Error',
                'message': str(e)
            })
        }