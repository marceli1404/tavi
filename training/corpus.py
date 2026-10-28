"""Original synthetic policy examples authored for Tavi, not user task outcomes.

Splits are authored separately. Training never imports heldout.py.
"""

# label, tier, training examples, validation examples. Labels are exact skill names.
GROUPS = [
('responsive-design', 'balanced', [
 'Fix the mobile menu overflowing a narrow screen', 'Adapt the layout for phones tablets and desktop',
 'Make this page responsive across viewport sizes', 'Cards should stack on small mobile screens',
 'Repair horizontal scrolling on a phone', 'Adjust the responsive layout when the browser shrinks'],
 ['Make the navigation fit on a tiny smartphone display']),
('accessibility-audit', 'balanced', [
 'Audit this interface for accessibility and WCAG issues', 'Check keyboard access and screen reader labels',
 'Find inaccessible controls and insufficient contrast', 'Review focus indicators for accessibility problems',
 'Assess WCAG compliance of the existing app', 'Identify accessibility defects in forms and buttons'],
 ['Check this screen for barriers affecting people using assistive technology']),
('webapp-testing', 'balanced', [
 'Test the local application using Playwright', 'Verify the login flow in a browser',
 'Run browser tests for the checkout form', 'Check console errors in the local web app',
 'Use browser automation to test interactions', 'Capture screenshots and verify the web app behaviour'],
 ['Exercise the local signup flow with an automated browser']),
('ui-design', 'balanced', [
 'Build a polished frontend interface in code', 'Create the dashboard UI with a strong visual style',
 'Implement a production quality web interface', 'Build the settings screen frontend',
 'Design and code an attractive application UI', 'Create a distinctive user interface for the app'],
 ['Implement the visual interface for our account settings']),
('copywriting', 'balanced', [
 'Write persuasive marketing copy for the homepage', 'Improve the landing page headline and benefits',
 'Rewrite the sales page to explain our product', 'Draft compelling product positioning copy',
 'Create marketing text for a new service', 'Write the hero headline and call to action'],
 ['Draft the sales messaging for our product launch page']),
('ux-writing', 'fast', [
 'Write a short validation error message', 'Improve the empty state text',
 'Suggest clearer button labels', 'Rewrite the password reset confirmation message',
 'Make this tooltip concise and helpful', 'Create interface microcopy for a failed upload'],
 ['Give me a clear message when a payment form field is empty']),
('website-copy-humanizer', 'balanced', [
 'Review website copy for robotic language after editing the site', 'Humanize the text on the modified website',
 'Run the six copy review passes on this updated site', 'Remove AI sounding phrases from the website copy',
 'Review the changed landing page for natural human wording', 'Improve the website language while preserving facts'],
 ['Make the wording on our updated site sound less machine generated']),
('color-system', 'balanced', [
 'Build an accessible product color palette', 'Define semantic colors and tonal scales',
 'Create a colour system with contrast compliant roles', 'Choose brand colours and semantic surface tokens',
 'Specify a consistent product palette', 'Design accessible colour roles for text and surfaces'],
 ['Define the app palette with accessible foreground and background colours']),
('typography-scale', 'balanced', [
 'Create a modular typography scale', 'Define font sizes weights and line heights',
 'Set a consistent type hierarchy for headings and body', 'Build a product font scale',
 'Specify heading sizes and paragraph line height', 'Establish a typography system for the interface'],
 ['Choose a consistent progression of font sizes for our product']),
('layout-grid', 'balanced', [
 'Define columns gutters and margins for a responsive grid', 'Create a twelve column page grid',
 'Specify desktop and mobile grid breakpoints', 'Set page columns and gutter widths',
 'Design the underlying layout grid', 'Establish a column structure for the dashboard'],
 ['Specify the page column count and spacing between columns']),
('form-design', 'balanced', [
 'Design a signup form with grouped fields and validation', 'Improve the field order in the checkout form',
 'Create a form with clear labels and errors', 'Plan the application form from start to completion',
 'Group related inputs in the registration form', 'Design validation and completion for a multi step form'],
 ['Organise the fields and validation behaviour of a registration form']),
('navigation-patterns', 'balanced', [
 'Choose tabs or sidebar navigation for the app', 'Design a navigation pattern matched to product structure',
 'Decide between a drawer and tab bar', 'Improve how users navigate between product sections',
 'Specify navigation behaviour for the application', 'Choose an app navigation model'],
 ['Should the product use a sidebar or a tab bar for navigation']),
('information-architecture', 'balanced', [
 'Organise the content structure and site hierarchy', 'Define clear labels and a sitemap',
 'Group product information into findable categories', 'Design the information architecture of our knowledge base',
 'Restructure the site hierarchy', 'Decide how content should be organised and labelled'],
 ['Arrange our help centre articles into understandable categories']),
('design-brief', 'balanced', [
 'Write a project brief with audience constraints and goals', 'Define the problem and success criteria before design',
 'Create a brief for a new product design project', 'Record stakeholders scope and deliverables in a design brief',
 'Document the audience and constraints for this project', 'Clarify the design project goals in a short brief'],
 ['Capture the project audience objectives constraints and expected deliverables']),
('a-b-test-design', 'balanced', [
 'Design an A/B experiment with a primary metric', 'Plan a split test for two signup variants',
 'Define the hypothesis and sample size for an experiment', 'Compare two checkout designs through an A/B test',
 'Choose experiment metrics and guardrails', 'Plan an A/B test with variants and success criteria'],
 ['Set up a controlled comparison between two onboarding variants']),
('data-visualization', 'balanced', [
 'Choose a chart type for these quantitative results', 'Design an accessible data chart',
 'Select visual encodings and axes for a graph', 'Show retention trends with an appropriate chart',
 'Choose marks labels and scales for a data visualisation', 'Compare categories in a readable chart'],
 ['Choose a clear chart and axis encoding for monthly sales figures']),
('user-flow-diagram', 'balanced', [
 'Draw the screen flow for a checkout journey', 'Map screens decisions and branches for password reset',
 'Create a user flow diagram for account signup', 'Diagram the paths between app screens',
 'Show the decision branches in the onboarding flow', 'Map the screen level journey from login to purchase'],
 ['Diagram how the visitor moves between signup screens and error branches']),
('usability-test-plan', 'balanced', [
 'Plan a usability study with participants and tasks', 'Write a usability testing plan and success metrics',
 'Define research questions for a usability test', 'Choose participants and sessions for interface testing',
 'Create the plan for a moderated usability study', 'Plan realistic tasks and metrics for user testing'],
 ['Plan sessions to observe users completing tasks in our prototype']),
('imagegen', 'balanced', [
 'Generate a product illustration image', 'Create a photorealistic picture of a mountain cabin',
 'Edit this photo to remove the background', 'Make a raster image of a futuristic city',
 'Create a cartoon portrait from this image', 'Generate a visual concept for a poster'],
 ['Create a realistic picture of a bicycle beside a lake']),
('openai-docs', 'balanced', [
 'Look up the official OpenAI API documentation', 'Explain Codex model configuration using official docs',
 'Find the current Responses API schema', 'Check official Codex CLI command options',
 'Verify OpenAI model settings and pricing documentation', 'Read the OpenAI docs for tool calling'],
 ['Check the documented configuration options for the Codex terminal client']),
('skill-creator', 'balanced', [
 'Create a reusable Codex skill for our workflow', 'Write a SKILL.md for reviewing pull requests',
 'Build a new local skill with scoped instructions', 'Update our custom skill to add references',
 'Design a reusable agent skill and its scripts', 'Package our recurring process as a Codex skill'],
 ['Turn our repeated review process into a reusable agent skill']),
('skill-installer', 'fast', [
 'Install this Codex skill from its GitHub repository', 'List the curated skills available to install',
 'Download and install the requested agent skill', 'Install a skill from the supplied repository path',
 'Add this approved skill to the local skill folder', 'Fetch the curated skill installer list'],
 ['Install the selected skill from the repository I provided']),
('reverse-engineer-anything', 'deep', [
 'Reverse engineer an unknown binary executable', 'Analyse the internals of a packaged Electron application',
 'Inspect a firmware image to recover its structure', 'Decompile a managed assembly and map its behaviour',
 'Investigate a native application binary format', 'Reverse engineer a program to understand its protocol'],
 ['Recover the structure and behaviour of an unfamiliar compiled application']),
('state-machine', 'balanced', [
 'Model component behaviour as a state machine', 'Define states events and transitions for the uploader',
 'Describe the valid state transitions of a payment flow', 'Create an explicit state model for this widget',
 'Map interaction states for a complex component', 'Specify a state transition table for the player'],
 ['Define the possible states and events of the file upload component']),
('motion-system', 'balanced', [
 'Define shared motion durations and easing tokens', 'Create animation rules including reduced motion handling',
 'Specify a consistent motion system', 'Set motion tokens for transitions across the product',
 'Define duration and easing vocabulary for UI animations', 'Build accessible product motion guidelines'],
 ['Set consistent animation timings and reduced motion behaviour']),
('search-ux', 'balanced', [
 'Design search results and zero result states', 'Improve search query input and filters',
 'Create a findable product search experience', 'Design search refinement and results presentation',
 'Plan zero results suggestions for our search box', 'Improve how people search within the application'],
 ['Design query refinement and empty results for the catalogue search']),
('error-handling-ux', 'balanced', [
 'Design recovery when a user action fails', 'Plan error prevention and recovery messages',
 'Improve how users recover from a failed payment', 'Design retry and recovery for network errors',
 'Specify error handling across the user flow', 'Help users understand and recover from application failures'],
 ['Plan how a person can retry and recover after an unsuccessful upload']),
('loading-states', 'balanced', [
 'Design skeleton screens while content loads', 'Improve the waiting experience for a slow operation',
 'Choose a progress indicator or spinner', 'Design loading and progressive reveal states',
 'Show useful feedback during a long running request', 'Create loading placeholders for a dashboard'],
 ['Choose a waiting indicator while the app fetches its content']),
('summarize-interview', 'balanced', [
 'Summarise this interview into themes and quotes', 'Extract insights from a user interview transcript',
 'Turn one research interview into action items', 'Find themes and supporting quotes in this transcript',
 'Summarize what the participant said during the interview', 'Analyse a single interview for key findings'],
 ['Extract the main findings and representative quotes from this user interview']),
('competitive-analysis', 'balanced', [
 'Compare UX patterns across rival products', 'Analyse competitor features and design gaps',
 'Review the strengths and weaknesses of competing apps', 'Compare our onboarding against three competitors',
 'Study rival products to identify design opportunities', 'Create a competitive UX analysis'],
 ['Compare the navigation and strengths of the competing products']),
]

# Model tier examples independent of skill metadata. These are policy labels,
# not measured claims that one commercial model performs best.
TIERS = {
 'fast': [
  'Say hello', 'What is two plus two', 'Convert ten centimetres to millimetres',
  'Give me five name ideas', 'Explain this single line of Python', 'Fix a typo in a comment',
  'Rename this local variable', 'Format this JSON object', 'Write a short thank you message',
  'Summarise this short paragraph', 'Sort this list of names', 'Translate a simple greeting',
  'Answer a quick factual question', 'Change the label from Save to Done',
  'List three synonyms for quick', 'Explain what a boolean is', 'Calculate twelve times seven',
  'Give me a one sentence definition', 'Make this sentence shorter', 'Suggest a filename'],
 'balanced': [
  'Implement a normal REST endpoint with validation', 'Fix a reproducible bug in this module',
  'Add unit tests for the parser', 'Refactor the helper function without changing its public API',
  'Build a small CLI utility', 'Implement pagination for a database query',
  'Review this pull request for correctness', 'Write a Python script to merge CSV files',
  'Add an accessible settings form', 'Debug why this application fails to start',
  'Create a deployment configuration for our app', 'Implement a feature across two modules',
  'Write documentation for a library', 'Add validation to the checkout endpoint',
  'Inspect a failing test and repair the underlying bug', 'Create a report from this dataset'],
 'deep': [
  'Investigate a nondeterministic distributed systems race condition',
  'Prove that this concurrent lock free algorithm is correct',
  'Design a multi region architecture with strict consistency guarantees',
  'Find the root cause of a rare deadlock across several services',
  'Plan a complex migration while preserving backward compatibility',
  'Audit the cryptographic protocol for subtle security flaws',
  'Analyse an intermittent memory corruption in native code',
  'Resolve a difficult performance regression spanning database and services',
  'Design a fault tolerant distributed consensus system',
  'Reason through a complex compiler optimisation correctness proof',
  'Diagnose an elusive production crash with conflicting evidence',
  'Compare architectural tradeoffs for a large system redesign',
  'Investigate a subtle security vulnerability across trust boundaries',
  'Solve this difficult mathematical proof step by step',
  'Design a complex database migration without service interruption',
  'Debug a hard to reproduce data corruption across concurrent writers'],
 'review': [
  'Do the thing', 'Continue with that', 'Fix it', 'Something is wrong',
  'You know what I mean', 'Handle the stuff', 'Make it better somehow',
  'Help', 'That one', 'Proceed as before', 'Do what we discussed', 'Finish this'],
}

EXTERNAL = [
 'Find a new agent skill online for Blender rigging because none is installed',
 'Search GitHub for a missing Kubernetes operator skill',
 'Discover an agent skill for CAD modelling from the internet',
 'Find a downloadable skill for a capability absent from our library',
 'Look online for a new skill to manage robotics simulation',
 'Search the internet for an agent skill that can process satellite imagery',
 'Find an installable SKILL.md for GIS workflows not covered locally',
 'Discover a new skill for a missing audio mastering workflow',
 'Search for a third party skill that supports our unfamiliar tool',
 'Look for an external skill to handle a missing integration',
 'Find a suitable skill repository for PCB design',
 'Discover a downloadable skill for 3D printing workflows',
 'Find new skills online for tasks that our installed skills cannot perform',
 'Search public repositories for an agent skill for chemistry simulation',
 'Find an internet skill for a missing tax reporting integration',
 'Look for a maintained skill for an unavailable CAD tool',
]

def records():
    rows = []
    for skill, tier, examples, validation in GROUPS:
        for split, prompts in [('train', examples), ('validation', validation)]:
            for i, prompt in enumerate(prompts):
                rows.append(dict(id=f'{skill}-{split}-{i}', prompt=prompt, tier=tier,
                                 skills=[skill], external=False, split=split, origin='agent-authored-synthetic'))
    for tier, examples in TIERS.items():
        for i, prompt in enumerate(examples):
            rows.append(dict(id=f'tier-{tier}-{i}', prompt=prompt, tier=tier, skills=[], external=False,
                             split='validation' if i % 5 == 4 else 'train', origin='agent-authored-synthetic'))
    for i, prompt in enumerate(EXTERNAL):
        rows.append(dict(id=f'external-{i}', prompt=prompt, tier='balanced', skills=[], external=True,
                         split='validation' if i % 5 == 4 else 'train', origin='agent-authored-synthetic'))
    return rows
