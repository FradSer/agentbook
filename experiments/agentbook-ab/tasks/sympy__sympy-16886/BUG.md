# sympy__sympy-16886

Morse encoding for "1" is not correct
The current Morse mapping in simpy.crypto.crypto contains an incorrect mapping of 
`"----": "1"`   

The correct mapping is `".----": "1"`.




---
Fix the bug in the sympy source. Do not edit any test file.
