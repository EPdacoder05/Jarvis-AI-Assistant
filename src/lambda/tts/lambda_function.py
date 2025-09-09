import json
import boto3
import uuid
import os
import logging
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
polly_client = boto3.client('polly')
s3_client = boto3.client('s3')

# Environment variables
BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')
API_KEY = os.environ.get('API_KEY')

def lambda_handler(event, context):
    """
    TTS Lambda function - converts text to speech using Amazon Polly
    and stores the audio file in S3, returning a presigned URL.
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
        
        # Extract text from request
        text = body.get('text', '').strip()
        voice_id = body.get('voice', 'Joanna')  # Default voice
        output_format = body.get('format', 'mp3')
        
        if not text:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Bad Request: text parameter is required'
                })
            }
        
        # Validate text length (Polly has limits)
        if len(text) > 3000:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Bad Request: text too long (max 3000 characters)'
                })
            }
        
        logger.info(f"Processing TTS request for text: {text[:50]}...")
        
        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        filename = f"tts_{timestamp}_{unique_id}.{output_format}"
        
        # Call Amazon Polly to synthesize speech
        polly_response = polly_client.synthesize_speech(
            Text=text,
            VoiceId=voice_id,
            OutputFormat=output_format,
            Engine='neural' if voice_id in ['Joanna', 'Matthew', 'Amy', 'Brian'] else 'standard'
        )
        
        # Upload audio to S3
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=filename,
            Body=polly_response['AudioStream'].read(),
            ContentType=f'audio/{output_format}',
            Metadata={
                'text': text[:200],  # Store first 200 chars of original text
                'voice': voice_id,
                'format': output_format,
                'created': datetime.now().isoformat()
            }
        )
        
        # Generate presigned URL (valid for 1 hour)
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': filename},
            ExpiresIn=3600  # 1 hour
        )
        
        logger.info(f"Successfully generated TTS audio: {filename}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'audio_url': presigned_url,
                'filename': filename,
                'voice': voice_id,
                'format': output_format,
                'text_length': len(text),
                'expires_in': 3600
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing TTS request: {str(e)}")
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

def cleanup_old_files():
    """
    Optional cleanup function to remove old audio files from S3
    Can be called by a separate scheduled Lambda
    """
    try:
        # List objects older than 24 hours
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix='tts_')
        
        if 'Contents' in response:
            for obj in response['Contents']:
                if obj['LastModified'].replace(tzinfo=None) < cutoff_time:
                    s3_client.delete_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                    logger.info(f"Deleted old file: {obj['Key']}")
        
        logger.info("Cleanup completed successfully")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")