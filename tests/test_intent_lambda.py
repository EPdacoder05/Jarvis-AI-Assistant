import unittest
import json
import os
import sys
from unittest.mock import Mock, patch, MagicMock

# Add the lambda source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src/lambda/intent'))

class TestIntentLambda(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment"""
        # Mock environment variables
        os.environ['API_KEY'] = 'test-api-key-123456'
        os.environ['HA_SECRET_NAME'] = 'test/homeassistant'
        os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
        
        # Import the lambda function after setting env vars
        global lambda_function
        import lambda_function
    
    def tearDown(self):
        """Clean up after tests"""
        # Reset the lambda_function module's global variables
        lambda_function._ha_credentials = None
    
    def test_parse_light_commands(self):
        """Test parsing of light control commands"""
        test_cases = [
            ("turn on the living room lights", "turn_on_light", {"room": "living room", "light_name": None}),
            ("turn off all lights", "turn_off_light", {"room": None, "light_name": None}),
            ("switch on the bedroom lamp", "turn_on_light", {"room": "bedroom", "light_name": None}),
            ("turn on kitchen lights", "turn_on_light", {"room": "kitchen", "light_name": None}),
            ("turn off the office desk lamp", "turn_off_light", {"room": "office", "light_name": "desk"}),
        ]
        
        for command, expected_intent, expected_params in test_cases:
            with self.subTest(command=command):
                intent, params = lambda_function.parse_command(command)
                self.assertEqual(intent, expected_intent)
                self.assertEqual(params['room'], expected_params['room'])
    
    def test_parse_temperature_commands(self):
        """Test parsing of temperature control commands"""
        test_cases = [
            ("set temperature to 72 degrees", "set_temperature", {"temperature": 72, "room": None}),
            ("change the bedroom temperature to 68", "set_temperature", {"temperature": 68, "room": "bedroom"}),
            ("set living room temperature to 75 degrees", "set_temperature", {"temperature": 75, "room": "living room"}),
        ]
        
        for command, expected_intent, expected_params in test_cases:
            with self.subTest(command=command):
                intent, params = lambda_function.parse_command(command)
                self.assertEqual(intent, expected_intent)
                self.assertEqual(params['temperature'], expected_params['temperature'])
                self.assertEqual(params['room'], expected_params['room'])
    
    def test_parse_media_commands(self):
        """Test parsing of media control commands"""
        test_cases = [
            ("play some music", "play_media", {"query": "some music", "type": "music"}),
            ("play jazz playlist", "play_media", {"query": "jazz playlist", "type": "music"}),
            ("stop the music", "stop_media", {}),
            ("pause media", "stop_media", {}),
        ]
        
        for command, expected_intent, expected_params in test_cases:
            with self.subTest(command=command):
                intent, params = lambda_function.parse_command(command)
                self.assertEqual(intent, expected_intent)
                if 'query' in expected_params:
                    self.assertEqual(params['query'], expected_params['query'])
    
    def test_parse_scene_commands(self):
        """Test parsing of scene activation commands"""
        test_cases = [
            ("activate movie night scene", "activate_scene", {"scene_name": "movie night"}),
            ("set party mode scene", "activate_scene", {"scene_name": "party mode"}),
            ("turn on romantic scene", "activate_scene", {"scene_name": "romantic"}),
        ]
        
        for command, expected_intent, expected_params in test_cases:
            with self.subTest(command=command):
                intent, params = lambda_function.parse_command(command)
                self.assertEqual(intent, expected_intent)
                if expected_params['scene_name']:
                    self.assertIn(expected_params['scene_name'], params['scene_name'])
    
    def test_parse_door_commands(self):
        """Test parsing of door/lock commands"""
        test_cases = [
            ("lock the front door", "lock_door", {"door": "front door"}),
            ("unlock the back door", "unlock_door", {"door": "back door"}),
            ("lock all doors", "lock_door", {"door": "front door"}),  # Default
        ]
        
        for command, expected_intent, expected_params in test_cases:
            with self.subTest(command=command):
                intent, params = lambda_function.parse_command(command)
                self.assertEqual(intent, expected_intent)
                self.assertEqual(params['door'], expected_params['door'])
    
    def test_parse_status_commands(self):
        """Test parsing of status query commands"""
        test_cases = [
            ("check lights status", "get_light_status", {}),
            ("what's the temperature status", "get_temperature_status", {}),
            ("check door status", "get_security_status", {}),
            ("status report", "get_general_status", {}),
        ]
        
        for command, expected_intent, _ in test_cases:
            with self.subTest(command=command):
                intent, params = lambda_function.parse_command(command)
                self.assertEqual(intent, expected_intent)
    
    def test_parse_unknown_commands(self):
        """Test parsing of unknown commands"""
        unknown_commands = [
            "make me a sandwich",
            "what's the meaning of life",
            "random gibberish command",
        ]
        
        for command in unknown_commands:
            with self.subTest(command=command):
                intent, params = lambda_function.parse_command(command)
                self.assertEqual(intent, "unknown_command")
                self.assertEqual(params['original_command'], command)
    
    def test_build_entity_ids(self):
        """Test entity ID building functions"""
        # Test light entity IDs
        self.assertEqual(
            lambda_function.build_light_entity_id("desk lamp", None),
            "light.desk_lamp"
        )
        self.assertEqual(
            lambda_function.build_light_entity_id(None, "living room"),
            "light.living_room_lights"
        )
        self.assertEqual(
            lambda_function.build_light_entity_id(None, None),
            "light.all_lights"
        )
        
        # Test climate entity IDs
        self.assertEqual(
            lambda_function.build_climate_entity_id("bedroom"),
            "climate.bedroom"
        )
        self.assertEqual(
            lambda_function.build_climate_entity_id(None),
            "climate.main_thermostat"
        )
    
    @patch('lambda_function.get_ha_credentials')
    @patch('lambda_function.requests.post')
    def test_execute_light_command(self, mock_post, mock_get_creds):
        """Test executing light control commands"""
        # Mock credentials
        mock_get_creds.return_value = {
            'url': 'https://homeassistant.local:8123',
            'token': 'test-token'
        }
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Test turn on light
        result = lambda_function.execute_ha_command(
            'turn_on_light',
            {'light_name': 'desk lamp', 'room': None}
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['intent'], 'turn_on_light')
        
        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn('/api/services/light/turn_on', call_args[0][0])
        self.assertEqual(call_args[1]['json']['entity_id'], 'light.desk_lamp')
    
    @patch('lambda_function.get_ha_credentials')
    @patch('lambda_function.requests.get')
    def test_execute_status_command(self, mock_get, mock_get_creds):
        """Test executing status query commands"""
        # Mock credentials
        mock_get_creds.return_value = {
            'url': 'https://homeassistant.local:8123',
            'token': 'test-token'
        }
        
        # Mock states response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                'entity_id': 'light.living_room',
                'state': 'on',
                'attributes': {}
            },
            {
                'entity_id': 'light.bedroom',
                'state': 'off',
                'attributes': {}
            }
        ]
        mock_get.return_value = mock_response
        
        # Test light status
        result = lambda_function.execute_ha_command('get_light_status', {})
        
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['total_lights'], 2)
        self.assertEqual(result['data']['lights_on'], 1)
    
    @patch('lambda_function.get_ha_credentials')
    @patch('lambda_function.requests.post')
    def test_ha_connection_error(self, mock_post, mock_get_creds):
        """Test handling of Home Assistant connection errors"""
        # Mock credentials
        mock_get_creds.return_value = {
            'url': 'https://homeassistant.local:8123',
            'token': 'test-token'
        }
        
        # Mock connection error
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError()
        
        result = lambda_function.execute_ha_command(
            'turn_on_light',
            {'light_name': 'test', 'room': None}
        )
        
        self.assertFalse(result['success'])
        self.assertIn('Cannot connect to Home Assistant', result['error'])
    
    def test_invalid_api_key(self):
        """Test request with invalid API key"""
        event = {
            'body': json.dumps({'command': 'turn on lights'}),
            'headers': {
                'x-api-key': 'invalid-key'
            }
        }
        
        response = lambda_function.lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 401)
        body = json.loads(response['body'])
        self.assertIn('Unauthorized', body['error'])
    
    def test_missing_command_parameter(self):
        """Test request with missing command parameter"""
        event = {
            'body': json.dumps({}),
            'headers': {
                'x-api-key': 'test-api-key-123456'
            }
        }
        
        response = lambda_function.lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('command parameter is required', body['error'])
    
    @patch('lambda_function.execute_ha_command')
    def test_successful_request(self, mock_execute):
        """Test successful command processing"""
        # Mock successful execution
        mock_execute.return_value = {
            'success': True,
            'message': 'Command executed successfully'
        }
        
        event = {
            'body': json.dumps({'command': 'turn on the lights'}),
            'headers': {
                'x-api-key': 'test-api-key-123456'
            }
        }
        
        response = lambda_function.lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['command'], 'turn on the lights')
        self.assertEqual(body['intent'], 'turn_on_light')
        self.assertTrue(body['result']['success'])
    
    @patch('lambda_function.secrets_client')
    def test_get_ha_credentials(self, mock_secrets):
        """Test retrieving Home Assistant credentials"""
        # Mock secrets response
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'url': 'https://homeassistant.local:8123',
                'token': 'secret-token-123'
            })
        }
        
        credentials = lambda_function.get_ha_credentials()
        
        self.assertEqual(credentials['url'], 'https://homeassistant.local:8123')
        self.assertEqual(credentials['token'], 'secret-token-123')
        
        # Test caching - second call shouldn't hit Secrets Manager
        lambda_function.get_ha_credentials()
        mock_secrets.get_secret_value.assert_called_once()
    
    def test_format_status_response(self):
        """Test status response formatting"""
        # Test light status formatting
        mock_states = [
            {'entity_id': 'light.living_room', 'state': 'on'},
            {'entity_id': 'light.bedroom', 'state': 'off'},
            {'entity_id': 'light.kitchen', 'state': 'on'},
            {'entity_id': 'sensor.temperature', 'state': '72'},  # Non-light entity
        ]
        
        result = lambda_function.format_status_response('get_light_status', mock_states, {})
        
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['total_lights'], 3)
        self.assertEqual(result['data']['lights_on'], 2)
        self.assertIn('light.living_room', result['data']['on_lights'])
        self.assertIn('light.kitchen', result['data']['on_lights'])
        self.assertNotIn('light.bedroom', result['data']['on_lights'])

if __name__ == '__main__':
    unittest.main()