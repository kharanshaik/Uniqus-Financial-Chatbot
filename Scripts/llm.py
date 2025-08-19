import os
import json
import boto3
import backoff
from loguru import logger
from dotenv import load_dotenv
from json_repair import repair_json

load_dotenv()

class LLM:
    def __init__(self):
        self.bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=os.getenv("REGION"),
            aws_access_key_id=os.getenv("ACCESSKEY"),
            aws_secret_access_key=os.getenv("SECRETKEY")
        )
    
    def _json(self, response):
        output = {}
        try:
            list_start = response.find("[")
            object_start = response.find("{")
            if list_start == -1 and object_start == -1:
                raise ValueError("No JSON structure found")
            start_index = min(list_start, object_start) if list_start != -1 and object_start != -1 else max(list_start, object_start)
            if start_index == list_start:
                end_index = response.rfind("]")
                response = response[start_index:end_index + 1]
            else:
                end_index = response.rfind("}")
                response = response[start_index:end_index + 1]
            try:
                output = eval(response)
            except:
                response = repair_json(response)
                output = json.loads(response)
        except Exception as e:
            logger.error(f"Failed to format in JSON: {str(e)}")
        return output

    @backoff.on_exception(
        backoff.expo, 
        (json.JSONDecodeError),
        max_tries=2,
        factor=2,
        on_backoff=lambda details: logger.warning(f"Retrying LLM call (attempt {details['tries']})")
    )        
    def _call_llm(self, system, context):
        """Make API call to Bedrock Claude Sonnet with retry mechanism"""
        ### Prepare the request body for Claude Sonnet
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 8192,
            "system": system,
            "messages": [
                {
                    "role": "user", 
                    "content": f"### Context ###\n{context}"
                }
            ],
            "temperature": 0
        }

        result = ""
        try:
            # Make the API call to Bedrock
            response = self.bedrock_client.invoke_model(
                modelId="us.anthropic.claude-sonnet-4-20250514-v1:0",
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json"
            )
            response_body = json.loads(response['body'].read())
            result = ' '.join([content['text'] for content in response_body['content']])
            result = self._json(result)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            raise
        return result