Create an app composed of the following parts

# First one 

On one folder I want to have a basic fastAPI that uses postgres and do the following:
- Have an endpoint to create a conversation
- Send message to a conversation
- Stream the content of that message to the end user

To answer the conversation use the response api from openAI
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-5",
    input="How much gold would it take to coat the Statue of Liberty in a 1mm layer?",
    reasoning={
        "effort": "minimal"
    }
)

print(response)

You have the documentation here https://platform.openai.com/docs/api-reference/responses, make sure to use the streaming

# Second one

Create another folder with the 3 following python files:
- On to test the the api with a basic requests.post 
- One to test the api in an async way
- One to simulate many users on the API running concurent queries (make the number of user a parameter)

# Third one

On the other folder I want an app in next js that uses the https://ai-sdk.dev/docs/ai-sdk-ui library to run the chat have a basic button to start a new conversation and stream the response
