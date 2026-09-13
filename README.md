# MaNan Notes

Personal engineering notes built with [Hugo](https://gohugo.io/) and [Hextra](https://imfing.github.io/hextra/), deployed by GitHub Actions.

## Structure

- `content/docs/` — PCIe and digital IC topic notes
- `content/blog/` — standalone chronological posts
- `content/tools/` — tool index
- `content/about/` — profile
- `static/` — downloadable scripts and static images
- `themes/hextra/` — pinned Hextra Git submodule
- `.github/workflows/pages.yml` — build and deployment workflow

## Local preview

```bash
git submodule update --init --recursive
hugo server
```

Existing public URLs for the IEEE 754 article, PCIe FFE topic, downloads, and about page are preserved through explicit Hugo front matter URLs.
