"""Synthetic new-skill training/validation. No acceptance examples are imported here."""
PROMPTS = {
 'tavi-decision': {
  'train': [
   'Use Tavi to choose a model and installed skills for this task',
   'Ask Tavi which Codex model should handle this coding request',
   'Get a Tavi recommendation for reasoning level and relevant skills',
   'Route this task through the locally trained Tavi decision model',
   'Have Tavi decide whether we need an external agent skill',
   'Tavi should select the model and skills for my workflow',
   'Choose the best available model and skill set with Tavi',
   'Use our custom decision AI Tavi to route this coding task',
   'Which model and skills does Tavi recommend for this job',
   'Run Tavi locally to assess the task and recommend tooling',
  ],
  'validation': [
   'Ask Tavi for a routing recommendation for the next task',
   'Use Tavi to recommend the Codex reasoning effort and skills',
  ],
  'negative_train': [
   'Train a new neural network using gradient descent',
   'Create a reusable skill from our review process',
   'Install the requested skill from this repository',
   'Check the official Codex documentation for model prices',
   'Find a new skill online for an unfamiliar CAD tool',
   'Explain how to build a model selection classifier',
   'Improve the Tavi source code and fix a bug in its CLI',
   'Write a Python unit test for this routing function',
   'Compare the structure of two machine learning models',
  ],
  'negative_validation': [
   'Fix an implementation bug in the Tavi training code',
   'Write documentation for a skill selection application',
   'Explain the supported model choices in the OpenAI API',
   'Install a new skill for a missing plugin integration',
  ]
 }
}


def records(names):
    rows = []
    for name in names:
        data = PROMPTS.get(name, {})
        for split in ('train', 'validation'):
            for i, prompt in enumerate(data.get(split, [])):
                rows.append(dict(id=f'extension-{name}-{split}-{i}', prompt=prompt, tier=None,
                                 skills=[name], external=False, split=split, origin='synthetic-new-skill'))
            for i, prompt in enumerate(data.get('negative_'+split, [])):
                rows.append(dict(id=f'extension-{name}-negative-{split}-{i}', prompt=prompt, tier=None,
                                 skills=[], external=False, split=split, origin='synthetic-new-skill-negative'))
    return rows
