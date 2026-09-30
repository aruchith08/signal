# SIGNAL 📡 — Web Application (Frontend)

## Overview

SIGNAL's web frontend is a **Vite + React + TypeScript** single-page application (SPA) that provides a modern, responsive dashboard for browsing opportunities, managing notifications, and personalizing preferences.

## Tech Stack

- **Build Tool:** Vite
- **Language:** TypeScript
- **UI Library:** React 18
- **Routing:** React Router v6
- **Styling:** Tailwind CSS
- **Icons:** Lucide React

## Getting Started

### Prerequisites

- Node.js 18+
- npm

### Installation

```bash
npm install
```

### Development

```bash
npm run dev
```

The application will be available at `http://localhost:5173`.

### Building

```bash
npm run build
```

The production build outputs to `dist/`.

### Preview Production Build

```bash
npm run preview
```

## Project Structure

```
src/
├── components/          # Reusable components
│   ├── common/         # Shared UI components (Button, Card, Badge, etc.)
│   ├── dashboard/      # Dashboard widgets
│   ├── feed/           # Feed components
│   └── layout/         # Layout components (Sidebar, Header)
├── contexts/           # React contexts (Auth, Toast, Theme)
├── pages/              # Page components
├── services/           # API service layer
└── types/              # TypeScript type definitions
```

## Features

- **Dashboard:** Overview metrics, recent opportunities, activity feed
- **Feed:** Filterable list of all opportunities with search
- **Opportunity Detail:** Full details, timeline, verification status
- **Saved:** Bookmark and track favorite opportunities
- **Review Queue:** Verification conflict review (reviewer/admin)
- **Notifications:** Alert preferences and history
- **Profile:** User profile and settings

## Environment Variables

Create a `.env` file:

```env
VITE_API_URL=http://localhost:8000/api/v1
```
