# Social preview (1280×640)

Upload `.github/social-preview.png` in GitHub:

**Settings → General → Social preview → Edit → Upload**

Used for link previews (LinkedIn, Slack, etc.). Regenerate from repo root:

```bash
python3 ../scripts/generate_github_social_previews.py
```

(Generator lives in the parent workspace `scripts/` folder when developing locally.)
