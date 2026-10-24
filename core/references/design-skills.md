# Design & Creative Skills — On-Demand Reference

These skill dirs live on disk but are NOT auto-loaded (removed from openclaw.json extraDirs
to keep the tool bundle small). When a video/design task comes in, add the relevant dirs
back to openclaw.json extraDirs temporarily, or read the SKILL.md files directly.

## Skill Directories (all under ~/.openclaw/workspace/skills/)

| Dir | Purpose |
|-----|---------|
| taste-skill/skills/taste-skill | Frontend design flagship (design-taste-frontend v2) |
| taste-skill/skills/brandkit | Brand kit / logo / identity |
| taste-skill/skills/soft-skill | High-end visual design |
| taste-skill/skills/minimalist-skill | Minimalist UI |
| taste-skill/skills/brutalist-skill | Industrial brutalist UI |
| taste-skill/skills/redesign-skill | Redesign existing projects |
| taste-skill/skills/imagegen-frontend-web | Web design reference images |
| taste-skill/skills/imagegen-frontend-mobile | Mobile design reference images |
| taste-skill/skills/image-to-code-skill | Design image → implementation |
| taste-skill/skills/output-skill | Full output enforcement |
| marketing-skills-guyaga/skills/video | AI video production (Remotion/HyperFrames/HeyGen) |
| marketing-skills-guyaga/skills/image | Marketing image / ad creative |
| cinetic/skills/cinetic | Cinematic motion design (Remotion + HyperFrames) — Python deps in ~/.venvs/cinetic |
| motion-design-skill/skills/motion-design | Motion design |
| barty-motion-graphics/skills/explainer-default | Explainer video (default) |
| barty-motion-graphics/skills/explainer-engaging | Explainer video (engaging) |
| barty-motion-graphics/skills/explainer-high-energy | Explainer video (high energy) |
| barty-motion-graphics/skills/motion-broll | B-roll motion |
| barty-motion-graphics/skills/object-separation | Object separation |
| barty-motion-graphics/skills/sound-effects | Sound effects |
| claude-motion-design/skill/motion-design | Motion design (Claude-style) |
| motion-graphics-skills-index/skills/motion-graphics | Motion graphics index |

## How to Use

For a one-off video/design task, read the relevant SKILL.md directly:
  read ~/.openclaw/workspace/skills/taste-skill/skills/taste-skill/SKILL.md

To temporarily re-add to the tool loader for a session, add the dir to
openclaw.json skills.load.extraDirs and restart the gateway. Remove again when done.
