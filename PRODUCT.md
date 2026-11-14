# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Next.js App Router on the web frontend, with a Python/FastAPI backend for authentication, library management, uploads, and streaming. Each account has a separate music library.

## Users

Primary users are people who want a personal music library they can organize and access from anywhere. They value control over their collections and clear, private account boundaries.

## Product Purpose

Vervfy is a web-based personal music library for uploading, organizing, and accessing music, playlists, and favorites, with account data isolated per user.

The landing page should clearly present Vervfy as a personal music library that is accessible from anywhere, while feeling polished, trustworthy, and private.

## Positioning

Vervfy is a personal music library, not a mass-market streaming catalog. Its value is bringing a person's music, playlists, favorites, lyrics, and artist details together in one place, accessible across sessions and devices.

## Operating Context

The product is used in a browser. It is not a general social streaming platform; it supports personal library management, playlists, playback, lyrics, artist details, and user-added music.

## Capabilities and Constraints

Confirmed capabilities include:

- personal music library upload and organization;
- playlist and favorites workflows;
- playback controls, queue behavior, and mini-player support;
- lyrics and artist metadata support;
- user auth and isolated per-account libraries;
- responsive desktop/tablet/mobile web experience;
- Web Audio visualizer and offline app shell support.

Constraints and non-claims:

- it is a web product, not a native mobile app;
- privacy and ownership are central differentiators;
- the landing page must not claim unsupported features or promise a product experience beyond the current implementation;
- existing product truth should remain faithful to the current Vervfy scope and behavior.

## Brand Commitments

Product name: Vervfy.

Brand commitments are rooted in personal music collections, privacy, and a modern but approachable music-app feel. The landing page should feel polished and user-friendly without presenting Vervfy as a mainstream streaming platform or a generic SaaS product.

## Evidence on Hand

- README.md documents the product and its main capabilities.
- `web/` contains the Next.js frontend and app structure.
- Existing product scope includes uploads, playlists, lyrics, artist metadata, responsive layout, and account isolation.

## Product Principles

- privacy first;
- user-owned libraries and control over the music experience;
- polished utility over generic SaaS styling;
- clarity and trust over hype;
- a modern, accessible personal-library experience.

## Accessibility & Inclusion

The product is designed for a general audience of music listeners. The landing page should be clear, readable, and accessible to a broad audience, while emphasizing ease of understanding and privacy. No product-specific accessibility burden beyond standard web accessibility was supplied.
