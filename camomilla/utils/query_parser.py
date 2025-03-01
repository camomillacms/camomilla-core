import re
from django.db.models import Q
from typing import List, Dict, Optional


class ConditionParser:
    CONDITION_PATTERN = re.compile(
        r"(\w+__\w+='[^']+'|\w+__\w+=\S+|\w+='[^']+'|\w+=\S+)"
    )
    LOGICAL_OPERATORS = {"AND", "OR"}

    __db_query: Optional[Q] = None

    def __init__(self, query: str):
        self.__db_query = None
        self.query = query

    def parse(self, query: str = None) -> Dict:
        """Parse the query or subquery. If no query is provided, use the instance's query."""
        if query is None:
            query = self.query

        tokens = self.tokenize(query)
        # If there's just one token and it's a dictionary (single condition), return it
        if len(tokens) == 1 and isinstance(tokens[0], dict):
            return tokens[0]
        return self.build_tree(tokens)

    def tokenize(self, query: str) -> List:
        tokens = []
        i = 0
        while i < len(query):
            if query[i] == "(":
                j = i + 1
                open_parens = 1
                while j < len(query) and open_parens > 0:
                    if query[j] == "(":
                        open_parens += 1
                    elif query[j] == ")":
                        open_parens -= 1
                    j += 1
                if open_parens == 0:
                    subquery = query[i + 1 : j - 1]
                    tokens.append(self.parse(subquery))  # Pass the subquery here
                    i = j
                else:
                    raise ValueError("Mismatched parentheses")
            elif query[i : i + 3] == "AND" or query[i : i + 2] == "OR":
                operator = "AND" if query[i : i + 3] == "AND" else "OR"
                tokens.append(operator)
                i += 3 if operator == "AND" else 2
            else:
                match = self.CONDITION_PATTERN.match(query[i:])
                if match:
                    condition = self.parse_condition(match.group())
                    tokens.append(condition)
                    i += match.end()
                else:
                    i += 1
        return tokens

    def parse_condition(self, condition: str) -> Optional[Dict]:
        """Parse a single condition into field lookup and value."""
        if "=" in condition:
            field_lookup, value = condition.split("=")
            value = value.strip("'").strip('"')  # Remove single or double quotes
            value = self.parse_value(value)  # Parse the value
            return {"field_lookup": field_lookup, "value": value}
        return None

    def parse_value(self, string: str):
        """Parse single condition values based on specific rules."""
        if string and string.startswith("[") and string.endswith("]"):
            string = [self.parse_value(substr) for substr in string[1:-1].split(",")]
        elif string and string.lower() in ["true", "false"]:
            string = string.lower() == "true"
        elif string and string.isdigit():
            string = int(string)
        return string

    def build_tree(self, tokens: List[str]) -> Dict:
        """Build a tree-like structure with operators and conditions."""
        if not tokens:
            return None

        output_stack = []
        operator_stack = []

        # Process each token in the query
        for token in tokens:
            if isinstance(token, dict):
                # Handle a single condition
                if operator_stack:
                    operator = operator_stack.pop()
                    if isinstance(output_stack[-1], dict):
                        output_stack[-1] = {
                            "operator": operator,
                            "conditions": [output_stack[-1], token],
                        }
                    else:
                        output_stack[-1]["conditions"].append(token)
                else:
                    output_stack.append(token)

            elif token in self.LOGICAL_OPERATORS:
                # Operator found (AND/OR), handle precedence
                operator_stack.append(token)

        # If only one item in output_stack, return it directly
        if len(output_stack) == 1:
            return output_stack[0]
        return {
            "operator": "AND",
            "conditions": output_stack,
        }  # Default to AND if no operators

    def to_q(self, parsed_tree: Dict) -> Q:
        """Convert parsed tree structure into Q objects."""
        if isinstance(parsed_tree, list):
            # If parsed_tree is a list, combine all conditions with AND by default
            q_objects = [self.to_q(cond) for cond in parsed_tree]
            combined_q = Q()
            for q_obj in q_objects:
                combined_q &= q_obj
            return combined_q

        if isinstance(parsed_tree, dict):
            if "field_lookup" in parsed_tree:
                # Base case: a single condition
                return Q(**{parsed_tree["field_lookup"]: parsed_tree["value"]})

            elif "operator" in parsed_tree and "conditions" in parsed_tree:
                operator = parsed_tree["operator"]
                conditions = parsed_tree["conditions"]

                q_objects = [self.to_q(cond) for cond in conditions]

                if operator == "AND":
                    combined_q = Q()
                    for q_obj in q_objects:
                        combined_q &= q_obj
                    return combined_q
                elif operator == "OR":
                    combined_q = Q()
                    for q_obj in q_objects:
                        combined_q |= q_obj
                    return combined_q
                else:
                    raise ValueError(f"Unknown operator: {operator}")

        raise ValueError("Parsed tree structure is invalid")

    def parse_to_q(self) -> Q:
        """Parse the query and convert to Q object."""
        parsed_tree = self.parse()
        if not parsed_tree:
            return Q()  # Return an empty Q if parsing fails
        return self.to_q(parsed_tree)

    @property
    def db_query(self) -> Q:
        if self.__db_query is None:
            self.__db_query = self.parse_to_q()
        return self.__db_query

    def __str__(self) -> str:
        return f"ConditionParser({self.db_query})"
