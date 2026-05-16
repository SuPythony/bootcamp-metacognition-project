"""Science graph tool — delegates to the math graph implementation.

The math graphing engine (matplotlib + sympy) works for any expression
and doesn't have domain-specific logic. Science graphs differ only in
how the agent frames the question to the student, not in rendering.
"""

from specializations.math.tools.graph import run  # re-export

__all__ = ["run"]
