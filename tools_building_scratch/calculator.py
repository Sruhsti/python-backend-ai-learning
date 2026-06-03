from openai import OpenAI
import os
import json

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(
    api_key=OPENAI_API_KEY
)


def calculator(a: int, b: int, operation: str) -> str:
    """
    Evaluates a mathematical expression and returns the result as a string.

    Args:
        a (int): The first operand.
        b (int): The second operand.
        operation (str): The operation to perform ("add", "subtract", "multiply", "divide").

    Returns:
        str: The result of the evaluated expression.
    """
    if operation == "add":
        return str(a + b)
    elif operation == "subtract":
        return str(a - b)
    elif operation == "multiply":
        return str(a * b)
    elif operation == "divide":
        if b == 0:
            return "Error: Division by zero"
        return str(a / b)
    else:
        return "Error: Invalid operation"
    

tools = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Perform basic arithmetic operations on two numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {
                        "type": "integer",
                        "description": "First number"
                    },
                    "b": {
                        "type": "integer",
                        "description": "Second number"
                    },
                    "operation": {
                        "type": "string",
                        "enum": [
                            "add",
                            "subtract",
                            "multiply",
                            "divide"
                        ],
                        "description": "Mathematical operation"
                    }
                },
                "required": ["a", "b", "operation"]
            }
        }
    }
]

def run_agent(user_message: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant. "
                "Use the calculator tool whenever math is required."
            )
        },
        {
            "role": "user",
            "content": user_message
        }
    ]

    while True:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            tools=tools
        )
        print("Response:", response)
        message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        if finish_reason == "tool_calls":
            messages.append(message)

            for tool_call in message.tool_calls:
                if tool_call.function.name == "calculator":
                    tool_args = json.loads(tool_call.function.arguments)
                    result = calculator(
                        a=tool_args["a"],
                        b=tool_args["b"],
                        operation=tool_args["operation"]
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })
        elif finish_reason == "stop":
            return message.content
        else:
             return (f"Unexpected finish reason: {finish_reason}")
        print("Updated messages:", messages)
        
answer = run_agent("What is 5 multiplied by 3?")
print(answer)
























#documantation calculator tool code

# from openai import OpenAI
# import ast
# import json
# import operator

# client = OpenAI()

# ALLOWED_BINARY_OPERATORS = {
#     ast.Add: operator.add,
#     ast.Sub: operator.sub,
#     ast.Mult: operator.mul,
#     ast.Div: operator.truediv,
#     ast.FloorDiv: operator.floordiv,
#     ast.Mod: operator.mod,
# }

# ALLOWED_UNARY_OPERATORS = {
#     ast.UAdd: operator.pos,
#     ast.USub: operator.neg,
# }

# def evaluate_node(node: ast.AST) -> int | float:
#     if isinstance(node, ast.Constant) and type(node.value) in (int, float):
#         return node.value

#     if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_BINARY_OPERATORS:
#         left = evaluate_node(node.left)
#         right = evaluate_node(node.right)
#         return ALLOWED_BINARY_OPERATORS[type(node.op)](left, right)

#     if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_UNARY_OPERATORS:
#         return ALLOWED_UNARY_OPERATORS[type(node.op)](evaluate_node(node.operand))

#     raise ValueError("Only numeric arithmetic is supported.")

# def safe_calculate(expression: str) -> str:
#     if len(expression) > 120:
#         raise ValueError("Expression too long.")
#     tree = ast.parse(expression, mode="eval")
#     result = evaluate_node(tree.body)
#     return str(result)

# # Define a tool
# tools = [
#     {
#         "type": "function",
#         "function": {
#             "name": "calculate",
#             "description": "Evaluate a math expression and return the result",
#             "strict": True,
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "expression": {
#                         "type": "string",
#                         "description": "A Python math expression, e.g. '2 + 3 * 4'"
#                     }
#                 },
#                 "required": ["expression"],
#                 "additionalProperties": False
#             }
#         }
#     }
# ]

# def calculate(expression: str) -> str:
#     """Evaluate a limited arithmetic expression."""
#     try:
#         return safe_calculate(expression)
#     except (SyntaxError, ValueError, ZeroDivisionError) as e:
#         return f"Error: {e}"

# # The agent loop
# def run_agent(user_message: str) -> str:
#     """Run the agent loop until it completes the task or runs out of iterations."""
#     messages = [
#         {"role": "system", "content": "You are a helpful assistant. "
#          "Use the calculate tool when you need to do math."},
#         {"role": "user", "content": user_message}
#     ]

#     while True:
#         response = client.chat.completions.create(
#             model="gpt-4.1",  # or another tool-capable model you can access
#             messages=messages,
#             tools=tools,
#         )

#         choice = response.choices[0]

#         # If the model wants to call a tool
#         if choice.finish_reason == "tool_calls":
#             assistant_message = choice.message.model_dump(exclude_none=True)
#             messages.append(assistant_message)
#             for tool_call in choice.message.tool_calls:
#                 args = json.loads(tool_call.function.arguments)
#                 result = calculate(args["expression"])

#                 # Add the tool result
#                 messages.append({
#                     "role": "tool",
#                     "tool_call_id": tool_call.id,
#                     "content": result,
#                 })
#         elif choice.finish_reason == "stop":
#             # Model is done, return the final answer
#             return choice.message.content
#         else:
#             return f"Agent stopped unexpectedly: {choice.finish_reason}"

# # Test it
# answer = run_agent("What is 42 * 17 + 389?")
# print(answer)