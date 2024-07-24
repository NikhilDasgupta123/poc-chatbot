from llama_index.core.tools.duckduckgo import DuckDuckGoSearchToolSpec
from llama_index.agent.openai import OpenAIAgent

tool_spec = DuckDuckGoSearchToolSpec()

agent = OpenAIAgent.from_tools(DuckDuckGoSearchToolSpec.to_tool_list())

agent.chat("What's going on with the superconductor lk-99")
agent.chat("what are the latest developments in machine learning")