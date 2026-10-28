"""New-skill acceptance cases fixed before extension training; same-author synthetic."""
CASES = [
 ('Ask Tavi to select the right model and skills for my coding task', True),
 ('Get Tavi to recommend a model and reasoning level for the next job', True),
 ('Use the local Tavi router to decide which installed skills apply', True),
 ('Let Tavi assess whether our task needs a downloadable agent skill', True),
 ('Run our Tavi decision AI and show its workflow recommendations', True),
 ('Use Tavi for model and skill selection before starting this task', True),
 ('Have the locally trained Tavi model route this request', True),
 ('Tell me which model and tools Tavi would use for this work', True),
 ('Write a new Codex skill for reviewing documents', False),
 ('Read official OpenAI documentation about model availability', False),
 ('Find a missing Blender skill on GitHub', False),
 ('Repair a bug in the Tavi neural training implementation', False),
 ('Explain how to train a text classifier in NumPy', False),
 ('Install the skill that I selected from the repository', False),
 ('Summarise this short paragraph about language models', False),
 ('Give me five names for a robot', False),
 ('Test the local checkout using a browser', False),
 ('Make the navigation menu fit a phone screen', False),
 ('Compare the latency of two hosted AI services', False),
 ('Define the architecture of a new skill marketplace', False),
]
GATES = {'recall': .875, 'precision': .875, 'specificity': .90}
