
#so here we will create 3 different tool and let the agent decide which one to use based on the user query. The tools will be:
from openai import OpenAI
import json
import logging
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
load_dotenv()

# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# print(OPENROUTER_API_KEY)


client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent")

MAX_ITERATIONS = 10
TOOL_REGISTRY = {}

ORDER_DB = {
    "12345": {
        "total": 89.99,
        "items": 3,
        "delivered": "2025-04-10"
    },
    "67890": {
        "total": 149.50,
        "items": 1,
        "delivered": "2025-05-01"
    }
}

POLICY_TEXT = "Returns accepted within 30 days of delivery."

def tool(func):
    """Decorator that registers a function as a tool."""
    TOOL_REGISTRY[func.__name__] = func
    return func

# tools
@tool
def get_current_date() -> str:
    """
    Returns the current date in ISO format (YYYY-MM-DD).
    Returns:
        str: The current date in ISO format.
    """
    return datetime.now(timezone.utc).date().isoformat()


@tool
def get_order_status(order_id: str) -> str:
    order = ORDER_DB.get(order_id)
    if not order:
        return f"Order ID {order_id} not found."
    return json.dumps(order)

@tool
def read_file(path: str) -> str:
    if path != "return_policy.txt":
        return f"Error: File '{path}' not found."

    return POLICY_TEXT


#helper functions 
def truncate_result(result: str, max_chars: int = 2000):

    if len(result) > max_chars:
        return result[:max_chars] + "\n...(truncated)"

    return result


def execute_tool_safe(name: str, args: dict):
    if name not in TOOL_REGISTRY:
        return (
            f"Error: Tool '{name}' does not exist."
        )
    try:
        return TOOL_REGISTRY[name](**args) # **args is used to unpack the arguments from the dictionary and pass them as keyword arguments to the function.
    except Exception as e:
        logger.exception(f"Error executing tool '{name}': {e}")
        return f"Error executing tool '{name}': {str(e)}"

# cost tracking
class CostLimitExceeded(RuntimeError):
    pass

class CostTracker:
    """Tracks LLM API usage costs across multiple calls."""
    
    def __init__(self, max_cost_usd: float = 0.01):
        self.max_cost = max_cost_usd
        self.total_cost = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.call_count = 0
    
    def track(self, response):
        """Calculate and accumulate the cost of a single API response."""
        usage = response.usage
        input_tokens = getattr(usage, "prompt_tokens", 0) 
        output_tokens = getattr(usage, "completion_tokens", 0)
        call_cost = getattr(usage, "cost", 0.0) or 0.0

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += call_cost
        self.call_count += 1

        logger.info(
            f"[Call {self.call_count}] "
            f"input_tokens={input_tokens}, "
            f"output_tokens={output_tokens}, "
            f"call_cost=${call_cost:.6f}, "
            f"total_cost=${self.total_cost:.6f}"
        )

        if self.total_cost > self.max_cost:
            raise CostLimitExceeded(
                f"Agent exceeded cost limit: ${self.total_cost:.6f} > ${self.max_cost:.6f}"
            )
        
    def summary(self):
        logger.info(
            f"[Cost Summary] "
            f"calls={self.call_count}, "
            f"total_input_tokens={self.total_input_tokens}, "
            f"total_output_tokens={self.total_output_tokens}, "
            f"total_cost=${self.total_cost:.6f}"
        )

#tool definations 
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": (
                "Look up an order by ID and return its details "
                "including delivery date, total, and item count."
            ),
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID to look up."
                    }
                },
                "required": ["order_id"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a company policy file. "
                "Use path 'return_policy.txt' to get the return policy."
            ),
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The filename to read."
                    }
                },
                "required": ["path"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_date",
            "description": "Get today's date in UTC as YYYY-MM-DD.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        }
    }
]


class Agent:
    """A production-oriented agent with guardrails and short-term memory."""
    
    def __init__(
        self,
        system_prompt: str,
        tools: list[dict],
        model="openai/gpt-oss-20b",
        max_cost_usd: float = 1.0,
    ):
        """Initialize the agent with constraints and available tools."""
        self.system_prompt = system_prompt
        self.tools = tools
        self.model = model
        self.cost_tracker = CostTracker(
            max_cost_usd,
        )
        self.messages = [{"role": "system", "content": system_prompt}]

    def _call_llm(self):
        """Call the model with the current conversation state."""
        return client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=self.tools,
        )
    
    def run(self, user_message: str) -> str:
        """Run the agent loop for a given user message."""
        self.messages.append({"role": "user", "content": user_message})
        
        for _ in range(MAX_ITERATIONS):
            response = self._call_llm()
            logger.info(f"LLM response: {response}")
            try:
                self.cost_tracker.track(response)
            except CostLimitExceeded as e:
                return str(e)

            choice = response.choices[0]
            
            if choice.finish_reason == "stop":
                self.messages.append(choice.message.model_dump(exclude_none=True))
                self.cost_tracker.summary()
                return choice.message.content or ""
            
            if choice.finish_reason != "tool_calls":
                self.cost_tracker.summary()
                return f"Agent stopped unexpectedly: {choice.finish_reason}"

            self.messages.append(choice.message.model_dump(exclude_none=True))
            
            for tool_call in choice.message.tool_calls or []:
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError as e:
                    result = (
                        f"Error parsing arguments: {e}. "
                        "Please try again with valid JSON."
                    )
                else:
                    result = execute_tool_safe(
                        tool_call.function.name, args
                    )
                logger.info(f"[Tool] {tool_call.function.name}({args}) → {result}")
                
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": truncate_result(result),
                })
        
        self.cost_tracker.summary()
        return "I reached the maximum number of steps. Here's what I found so far..."
    


if __name__ == "__main__":
    system_prompt="""
You are a helpful order support assistant.

Available tools:
- get_order_status
- read_file
- get_current_date

Use tools whenever needed.
"""
    agent = Agent(system_prompt, TOOLS)

    user_message = "Can I return my order 12345?"
    result = agent.run(user_message)
    print(result)
































#here we compund tool means we have single tool which is check_return_eligibility but internally it uses multiple helper functions to get the order status, read the return policy, extract the return window, and calculate eligibility. This allows us to keep the tool interface simple while still performing complex operations under the hood.
# from openai import OpenAI
# import json
# import logging
# from datetime import datetime, timedelta, timezone
# import os
# import re
# from dotenv import load_dotenv
# load_dotenv()

## OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


# client = OpenAI(
    # api_key=OPENROUTER_API_KEY,
    # base_url="https://openrouter.ai/api/v1")

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger("agent")

# MAX_ITERATIONS = 10
# TOOL_REGISTRY = {}

# ORDER_DB = {
#     "12345": {
#         "total": 89.99,
#         "items": 3,
#         "delivered": "2025-04-10"
#     },
#     "67890": {
#         "total": 149.50,
#         "items": 1,
#         "delivered": "2025-05-01"
#     }
# }

# POLICY_TEXT = "Returns accepted within 30 days of delivery."

# def tool(func):
#     """Decorator that registers a function as a tool."""
#     TOOL_REGISTRY[func.__name__] = func
#     return func

# # tools

# def get_current_date() -> str:
#     """
#     Returns the current date in ISO format (YYYY-MM-DD).
#     Returns:
#         str: The current date in ISO format.
#     """
#     return datetime.now(timezone.utc).date().isoformat()



# def get_order_status(order_id: str) -> str:
#     order = ORDER_DB.get(order_id)
#     if not order:
#         return f"Order ID {order_id} not found."
#     return json.dumps(order)

# def read_file(path: str) -> str:
#     if path != "return_policy.txt":
#         return f"Error: File '{path}' not found."

#     return POLICY_TEXT


# def extract_return_window_days(policy_text: str) -> int:
#     match = re.search(r"within (\d+) days", policy_text)
#     if match is None:
#         raise ValueError("Policy does not include a return window.")
#     return int(match.group(1))


# @tool
# def check_return_eligibility(order_id: str) -> str:

#     order_json = get_order_status(order_id)
#     if order_json.startswith("Error"):
#         return order_json
    
#     order = json.loads(order_json)

#     delivered_date = datetime.fromisoformat(order.get("delivered")).date()

#     policy_text = read_file("return_policy.txt")
#     if policy_text.startswith("Error"):
#         return policy_text
    
#     window_days = extract_return_window_days(policy_text)

#     current_date = datetime.fromisoformat(get_current_date()).date()

#     expiry_date = delivered_date + timedelta(days=window_days)

#     if current_date <= expiry_date:
#         return (
#             f"Eligible for return "
#             f"{expiry_date.isoformat()} is the last day to return the order."
#         )
#     else:
#         return (
#             f"Not eligible for return "
#             f"{expiry_date.isoformat()} was the last day to return the order."
#         )



# #helper functions 
# def truncate_result(result: str, max_chars: int = 2000):

#     if len(result) > max_chars:
#         return result[:max_chars] + "\n...(truncated)"

#     return result


# def execute_tool_safe(name: str, args: dict):
#     if name not in TOOL_REGISTRY:
#         return (
#             f"Error: Tool '{name}' does not exist."
#         )
#     try:
#         return TOOL_REGISTRY[name](**args) # **args is used to unpack the arguments from the dictionary and pass them as keyword arguments to the function.
#     except Exception as e:
#         logger.exception(f"Error executing tool '{name}': {e}")
#         return f"Error executing tool '{name}': {str(e)}"

# # cost tracking
# class CostLimitExceeded(RuntimeError):
#     pass

#class CostTracker:
    # """Tracks LLM API usage costs across multiple calls."""
    
    # def __init__(self, max_cost_usd: float = 0.01):
    #     self.max_cost = max_cost_usd
    #     self.total_cost = 0.0
    #     self.total_input_tokens = 0
    #     self.total_output_tokens = 0
    #     self.call_count = 0
    
    # def track(self, response):
    #     """Calculate and accumulate the cost of a single API response."""
    #     usage = response.usage
    #     input_tokens = getattr(usage, "prompt_tokens", 0) 
    #     output_tokens = getattr(usage, "completion_tokens", 0)
    #     call_cost = getattr(usage, "cost", 0.0) or 0.0

    #     self.total_input_tokens += input_tokens
    #     self.total_output_tokens += output_tokens
    #     self.total_cost += call_cost
    #     self.call_count += 1

    #     logger.info(
    #         f"[Call {self.call_count}] "
    #         f"input_tokens={input_tokens}, "
    #         f"output_tokens={output_tokens}, "
    #         f"call_cost=${call_cost:.6f}, "
    #         f"total_cost=${self.total_cost:.6f}"
    #     )

    #     if self.total_cost > self.max_cost:
    #         raise CostLimitExceeded(
    #             f"Agent exceeded cost limit: ${self.total_cost:.6f} > ${self.max_cost:.6f}"
    #         )
        
    # def summary(self):
    #     logger.info(
    #         f"[Cost Summary] "
    #         f"calls={self.call_count}, "
    #         f"total_input_tokens={self.total_input_tokens}, "
    #         f"total_output_tokens={self.total_output_tokens}, "
    #         f"total_cost=${self.total_cost:.6f}"
    #     )

# #tool definations 
# TOOLS = [
#     {
#         "type": "function",
#         "function": {
#             "name": "check_return_eligibility",
#             "description": (
#                 "Check whether an order is eligible for return. "
#                 "Internally fetches order details, the return policy, "
#                 "and the current date to determine eligibility."
#             ),
#             "strict": True,
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "order_id": {
#                         "type": "string",
#                         "description": "The order ID to check."
#                     }
#                 },
#                 "required": ["order_id"],
#                 "additionalProperties": False
#             }
#         }
#     }
# ]


# class Agent:
#     """A production-oriented agent with guardrails and short-term memory."""
    
#     def __init__(
#         self,
#         system_prompt: str,
#         tools: list[dict],
#         model="openai/gpt-oss-20b",
#         max_cost_usd: float = 1.0

#     ):
#         """Initialize the agent with constraints and available tools."""
#         self.system_prompt = system_prompt
#         self.tools = tools
#         self.model = model
#         self.cost_tracker = CostTracker(
#             max_cost_usd
#         )
#         self.messages = [{"role": "system", "content": system_prompt}]

#     def _call_llm(self):
#         """Call the model with the current conversation state."""
#         return client.chat.completions.create(
#             model=self.model,
#             messages=self.messages,
#             tools=self.tools,
#         )
    
#     def run(self, user_message: str) -> str:
#         """Run the agent loop for a given user message."""
#         self.messages.append({"role": "user", "content": user_message})
        
#         for _ in range(MAX_ITERATIONS):
#             response = self._call_llm()
#             logger.info(f"LLM response: {response}")
#             try:
#                 self.cost_tracker.track(response)
#             except CostLimitExceeded as e:
#                 return str(e)

#             choice = response.choices[0]
            
#             if choice.finish_reason == "stop":
#                 self.messages.append(choice.message.model_dump(exclude_none=True))
#                 self.cost_tracker.summary() 
#                 return choice.message.content or ""
            
#             if choice.finish_reason != "tool_calls":
#                 self.cost_tracker.summary()
#                 return f"Agent stopped unexpectedly: {choice.finish_reason}"

#             self.messages.append(choice.message.model_dump(exclude_none=True))
            
#             for tool_call in choice.message.tool_calls or []:
#                 try:
#                     args = json.loads(tool_call.function.arguments)
#                 except json.JSONDecodeError as e:
#                     result = (
#                         f"Error parsing arguments: {e}. "
#                         "Please try again with valid JSON."
#                     )
#                 else:
#                     result = execute_tool_safe(
#                         tool_call.function.name, args
#                     )
#                logger.info(f"[Tool] {tool_call.function.name}({args}) → {result}")
                
#                 self.messages.append({
#                     "role": "tool",
#                     "tool_call_id": tool_call.id,
#                     "content": truncate_result(result),
#                 })
# 
#         self.cost_tracker.summary() 
#         return "I reached the maximum number of steps. Here's what I found so far..."
    


# if __name__ == "__main__":
#     system_prompt = """
# You are a helpful order support assistant.

# Available tools:
# - check_return_eligibility

# Use tools whenever needed.
# """
#     agent = Agent(system_prompt, TOOLS)

#     user_message = "Can I return my order 12345?"
#     result = agent.run(user_message)
#     print(result)






