
import enum
from dotenv import load_dotenv

load_dotenv()


class SearchEngine(enum.Enum):
    TAVILY = "tavily"
    BOCHA = "bocha"



# Tool configuration loaded from conf.yaml
from src.config.settings import get_search_api

SELECTED_SEARCH_ENGINE = get_search_api()
