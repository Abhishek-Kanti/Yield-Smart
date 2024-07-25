import os
import json
import requests

from PIL import Image
from dotenv import load_dotenv
from django.conf import settings
from duckduckgo_search import DDGS

from langchain_cohere import CohereEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

ddg = DDGS()
embedding_function=CohereEmbeddings()

load_dotenv()
os.environ['GOOGLE_API_KEY'] = os.getenv('GOOGLE_API_KEY')

conversation = []
def set_conversation(conv: list):
    global conversation
    conversation = conv

@tool
def history() -> list:
    "All the conversation details between user and AI"
    global conversation
    return conversation['texts']

history.name = "history"
history.description = "All the conversation details between user and AI"

@tool
def web_search_tool(query: str) -> list:
    """Retrieve relevant info from web.
    Args:
        query (str): query for searching on web
    """
    try:
        results = ddg.text(query, max_results=3)
        urls = [i["href"] for i in results]
    except Exception as e:
        return f"Unavle to reach ddg.\nException{e}"
    
    results = WebBaseLoader(urls).load()

    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=512, chunk_overlap=64
    )
    doc_splits = text_splitter.split_documents(results)
    vectorstore = FAISS.from_documents(
        documents=doc_splits,
        embedding=embedding_function,
    )
    vectorstore_retriever = vectorstore.as_retriever()
    docs = vectorstore_retriever.invoke(query)
    return [doc.page_content for doc in docs ]

web_search_tool.name = "Web Search"
web_search_tool.description = "Retrieve relevant info from web."

class web_search_inputs(BaseModel):
   query: str = Field(description="query for searching on web")

web_search_tool.args_schema = web_search_inputs

@tool
def weather_tool(area: str) -> dict:
    """Gets the weather and other details for a given area.
    Args:
        area (str): The area to get the weather for.
    """
    weather_api_key = os.getenv('WEATHER_API_KEY')
    link = f"http://api.weatherapi.com/v1/current.json?key={weather_api_key}&q={area}&aqi=yes"
    response = requests.get(link)
    return json.loads(response.text)

weather_tool.name = "weather"
weather_tool.description = "Get weather report with other details of the given area"

class weather_inputs(BaseModel):
   area: str = Field(description="area name")
weather_tool.args_schema = weather_inputs

weather_tool_details = """
weather_report_tool :
Check for any area mentioned in current input, if not then check for any previous area name mentioned in history.
If you confirm that no area is mention in current input nor in history, then ask for the area name to the user.
This tool provide more details information that just the weather report, for any of the inforamtion bellow you can use this tool
Details:
    name: 
    region: 
    country: 
    lat: 
    lon: 
    tz_id: 
    localtime_epoch: 
    localtime: 
  current:
    last_updated_epoch: 
    last_updated: 
    temp_c: 
    temp_f: 
    is_day: 
    condition:
      text: 
      icon: 
      code: 
    wind_mph: 
    wind_kph: 
    wind_degree: 
    wind_dir: 
    pressure_mb:
    pressure_in: 
    precip_mm: 
    precip_in:
    humidity:
    cloud: 
    feelslike_c: 
    feelslike_f: 
    windchill_c: 
    windchill_f: 
    heatindex_c: 
    heatindex_f: 
    dewpoint_c: 
    dewpoint_f: 
    vis_km: 
    vis_miles: 
    uv: 
    gust_mph: 
    gust_kph: 
    air_quality: 
"""

@tool
def visual_tool(prompt: str, image_url: str) -> str:
    """Responding on image url input
    Args:
        prompt (str): prompt input
        image_url (str): url input
    """
    image_path = 'saved_image.jpg'
    response = requests.get(image_url)
    if response.status_code == 200:
        pass
        with open(image_path, "wb") as f:
            f.write(response.content)
    else:
        return(f"Error fetching image. Status code: {response.status_code}")

    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_path}},
        ],
    )
    model = ChatGoogleGenerativeAI(model="gemini-1.5-flash")
    try:
        response = model.invoke([message])
        print("Respond succesfully: ", response.content)
        return response.content
    except Exception as e: 
        print("Error found : ",e)
        return e

visual_tool.name = "visual"
visual_tool.description = "Get image details on given prompt"

class visual_inputs(BaseModel):
   prompt: str = Field(description="prompt for image")
   image_url: str = Field(description="url for image")
visual_tool.args_schema = visual_inputs

visual_tool_details = """
visual_tool:
This tool use a image url and a prompt as input.
If user send any image url in image, generate a prompt to get details result. Arrenge the output and send it in most user friendly way to user.
For any follow up questions on any previous image, use the previous image url for this tool to respond to that follow up question.
"""

TOOLS = [history, web_search_tool, weather_tool, visual_tool]
TOOS_DETAILS = """
history:
If you think you need more history of conversation, then use this tool to get all previous conversation history.

web_search_tool:
When you felt like you need a web information to fullfill your response to user input use this tool.
Make your own search queary to retrive the most revent inforamation from web.

visual_tool:
This tool use a image url and a prompt as input.
If user send any image url in image, generate a prompt to get details result. Arrenge the output and send it in most user friendly way to user.
For any follow up questions on any previous image, use the previous image url for this tool to respond to that follow up question.

weather_report_tool :
Check for any area mentioned in current input, if not then check for any previous area name mentioned in history.
If you confirm that no area is mention in current input nor in history, then ask for the area name to the user.
This tool provide more details information that just the weather report, for any of the inforamtion bellow you can use this tool
Details:
    name: 
    region: 
    country: 
    lat: 
    lon: 
    tz_id: 
    localtime_epoch: 
    localtime: 
  current:
    last_updated_epoch: 
    last_updated: 
    temp_c: 
    temp_f: 
    is_day: 
    condition:
      text: 
      icon: 
      code: 
    wind_mph: 
    wind_kph: 
    wind_degree: 
    wind_dir: 
    pressure_mb:
    pressure_in: 
    precip_mm: 
    precip_in:
    humidity:
    cloud: 
    feelslike_c: 
    feelslike_f: 
    windchill_c: 
    windchill_f: 
    heatindex_c: 
    heatindex_f: 
    dewpoint_c: 
    dewpoint_f: 
    vis_km: 
    vis_miles: 
    uv: 
    gust_mph: 
    gust_kph: 
    air_quality: 
"""