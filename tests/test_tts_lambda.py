import unittest
import json
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

# Add the lambda source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src/lambda/tts'))

class TestTTSLambda(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment"""
        # Mock environment variables
        os.environ['S3_BUCKET_NAME'] = 'test-bucket'
        os.environ['API_KEY'] = 'test-api-key-123456'
        os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
        
        # Import the lambda function after setting env vars
        global lambda_function
        import lambda_function
    
    def tearDown(self):
        """Clean up after tests"""
        # Reset the lambda_function module's global variables
        lambda_function._ha_credentials = None
    
    @patch('lambda_function.polly_client')
    @patch('lambda_function.s3_client')
    def test_successful_tts_request(self, mock_s3, mock_polly):
        """Test successful TTS request"""
        # Mock Polly response
        mock_audio_stream = Mock()
        mock_audio_stream.read.return_value = b'fake_audio_data'
        mock_polly.synthesize_speech.return_value = {
            'AudioStream': mock_audio_stream
        }
        
        # Mock S3 response
        mock_s3.generate_presigned_url.return_value = 'https://s3.example.com/audio.mp3'
        
        # Create test event
        event = {
            'body': json.dumps({
                'text': 'Hello, this is a test message',
                'voice': 'Joanna',
                'format': 'mp3'
            }),
            'headers': {
                'x-api-key': 'test-api-key-123456'
            }
        }
        
        # Call the lambda function
        response = lambda_function.lambda_handler(event, {})
        
        # Assertions
        self.assertEqual(response['statusCode'], 200)
        
        body = json.loads(response['body'])
        self.assertTrue(body['success'])
        self.assertIn('audio_url', body)
        self.assertEqual(body['voice'], 'Joanna')
        self.assertEqual(body['format'], 'mp3')
        
        # Verify Polly was called correctly
        mock_polly.synthesize_speech.assert_called_once()
        call_args = mock_polly.synthesize_speech.call_args[1]
        self.assertEqual(call_args['Text'], 'Hello, this is a test message')
        self.assertEqual(call_args['VoiceId'], 'Joanna')
        self.assertEqual(call_args['OutputFormat'], 'mp3')
        
        # Verify S3 operations
        mock_s3.put_object.assert_called_once()
        mock_s3.generate_presigned_url.assert_called_once()
    
    def test_invalid_api_key(self):
        """Test request with invalid API key"""
        event = {
            'body': json.dumps({'text': 'Hello'}),
            'headers': {
                'x-api-key': 'invalid-key'
            }
        }
        
        response = lambda_function.lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 401)
        body = json.loads(response['body'])
        self.assertIn('Unauthorized', body['error'])
    
    def test_missing_api_key(self):
        """Test request with missing API key"""
        event = {
            'body': json.dumps({'text': 'Hello'}),
            'headers': {}
        }
        
        response = lambda_function.lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 401)
        body = json.loads(response['body'])
        self.assertIn('Unauthorized', body['error'])
    
    def test_missing_text_parameter(self):
        """Test request with missing text parameter"""
        event = {
            'body': json.dumps({}),
            'headers': {
                'x-api-key': 'test-api-key-123456'
            }
        }
        
        response = lambda_function.lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('text parameter is required', body['error'])
    
    def test_text_too_long(self):
        """Test request with text that's too long"""
        long_text = 'a' * 3001  # Exceeds 3000 character limit
        
        event = {
            'body': json.dumps({'text': long_text}),
            'headers': {
                'x-api-key': 'test-api-key-123456'
            }
        }
        
        response = lambda_function.lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('text too long', body['error'])
    
    def test_default_voice_and_format(self):
        """Test request with default voice and format"""
        with patch('lambda_function.polly_client') as mock_polly, \
             patch('lambda_function.s3_client') as mock_s3:
            
            # Mock responses
            mock_audio_stream = Mock()
            mock_audio_stream.read.return_value = b'fake_audio_data'
            mock_polly.synthesize_speech.return_value = {
                'AudioStream': mock_audio_stream
            }
            mock_s3.generate_presigned_url.return_value = 'https://s3.example.com/audio.mp3'
            
            event = {
                'body': json.dumps({'text': 'Hello'}),
                'headers': {
                    'x-api-key': 'test-api-key-123456'
                }
            }
            
            response = lambda_function.lambda_handler(event, {})
            
            self.assertEqual(response['statusCode'], 200)
            
            # Check that defaults were used
            call_args = mock_polly.synthesize_speech.call_args[1]
            self.assertEqual(call_args['VoiceId'], 'Joanna')  # Default voice
            self.assertEqual(call_args['OutputFormat'], 'mp3')  # Default format
    
    @patch('lambda_function.polly_client')
    def test_polly_error_handling(self, mock_polly):
        """Test error handling when Polly fails"""
        mock_polly.synthesize_speech.side_effect = Exception('Polly service error')
        
        event = {
            'body': json.dumps({'text': 'Hello'}),
            'headers': {
                'x-api-key': 'test-api-key-123456'
            }
        }
        
        response = lambda_function.lambda_handler(event, {})
        
        self.assertEqual(response['statusCode'], 500)
        body = json.loads(response['body'])
        self.assertIn('Internal Server Error', body['error'])
    
    def test_direct_event_format(self):
        """Test handling of direct event format (not API Gateway)"""
        with patch('lambda_function.polly_client') as mock_polly, \
             patch('lambda_function.s3_client') as mock_s3:
            
            # Mock responses
            mock_audio_stream = Mock()
            mock_audio_stream.read.return_value = b'fake_audio_data'
            mock_polly.synthesize_speech.return_value = {
                'AudioStream': mock_audio_stream
            }
            mock_s3.generate_presigned_url.return_value = 'https://s3.example.com/audio.mp3'
            
            # Direct event format (not wrapped in 'body')
            event = {
                'text': 'Hello direct event',
                'voice': 'Matthew',
                'headers': {
                    'x-api-key': 'test-api-key-123456'
                }
            }
            
            response = lambda_function.lambda_handler(event, {})
            
            self.assertEqual(response['statusCode'], 200)
            body = json.loads(response['body'])
            self.assertEqual(body['voice'], 'Matthew')
    
    @patch('lambda_function.s3_client')
    def test_cleanup_old_files(self, mock_s3):
        """Test the cleanup function"""
        from datetime import datetime, timedelta
        
        # Mock S3 list response with old and new files
        old_time = datetime.now() - timedelta(hours=25)
        new_time = datetime.now() - timedelta(hours=1)
        
        mock_s3.list_objects_v2.return_value = {
            'Contents': [
                {
                    'Key': 'tts_old_file.mp3',
                    'LastModified': old_time
                },
                {
                    'Key': 'tts_new_file.mp3',
                    'LastModified': new_time
                }
            ]
        }
        
        lambda_function.cleanup_old_files()
        
        # Verify that only the old file was deleted
        mock_s3.delete_object.assert_called_once_with(
            Bucket='test-bucket',
            Key='tts_old_file.mp3'
        )

if __name__ == '__main__':
    unittest.main()