# AgriRoute

A responsive, frontend-only agricultural innovation prototype for SVIC and the theme **Samriddh Annadata, Samriddh Bharat**. Built with React, Vite, JavaScript/JSX, Tailwind CSS, React Router and Lucide React. All inventory, allocations and scores are local sample data. No backend, database, authentication, real API, map service or fake server calls.

## Run locally

Use Node.js 20.19+ or 22.12+.

```sh
npm install
npm run dev
```

Open the URL printed by Vite. `npm run build` creates `dist`; `npm run preview` previews that build. Internet is needed to install dependencies; runtime requires no external services, fonts or images.

## Demo roles and routes

- `/` — landing page, workflow and illustrative impact
- `/login` — demo role selection, also used to switch roles
- `/farmer/dashboard` — Arun Kumar’s summary and active batches
- `/farmer/add-produce` — validated form, draft storage and image preview
- `/farmer/produce` — search and status filters
- `/farmer/produce/:id` — batch lifecycle and traceability
- `/farmer/matches` — ranked sample primary buyers and quantity acceptance
- `/farmer/rerouting` — routing decision and guided showcase
- `/buyer/dashboard` — primary sourcing overview
- `/buyer/requirements` — locally saved requirements
- `/buyer/available-produce` — editable required quantity and partial allocation dialog
- `/processor/dashboard` — alternative utilization overview
- `/processor/rerouted-produce` — eligible batches and confirmation
- `/admin/dashboard` — sample network totals, local allocation charts and activity

## Judge demonstration

The initial showcase is at 850 kg sold and 150 kg awaiting rerouting. For the full sequence:

1. In Dynamic routing, click **Restart demo**, then **Restart with fresh inventory**. This restores sample inventory and starts tomatoes at 1,000 kg, Grade A, low risk. **Start at routing decision** restores the initial 850 kg sold / 150 kg high-urgency showcase instead.
2. Open Available produce as Buyer. Use FreshMart Wholesale as the demo buying organization, enter 600 kg and accept the tomato listing. Confirm the dialog showing 400 kg remaining.
3. Choose Green Basket Retail as the demo buying organization (250 kg) and accept the tomato listing. There are now 150 kg remaining. Primary matching continues; partial sales alone never activate rerouting.
4. In Dynamic routing, click **Simulate Day 3**. This explicitly simulates repeated unmatched primary attempts, reduced shelf life and Grade B. Rerouting becomes eligible.
5. Route the remaining 150 kg to South Foods Processing (200 kg maximum capacity). Confirm the compatible destination. The batch now shows 850 kg primary sales, 150 kg alternative utilization and 0 kg unutilized.
6. View the batch journey or switch to Admin to see shared local updates.

All roles share one demo inventory, rather than isolated accounts. Requirement records are stored locally; rankings remain illustrative and are not computed from submitted requirements. Sample buyer cards represent multiple organizations in the demonstration. Processor acceptance simulates a destination review, not a food safety certification. Visual assessment is an explicitly labeled fixed sample and does not analyze image content. Risk uses demo progression and stated cosmetic eligibility, not ML. Uploaded images are previewed in memory; drafts persist form fields, not images. Restart restores all sample batches and removes added produce, while preserving requirements. localStorage retains inventory, requirements, role and theme across refreshes. Clear browser storage to erase all demo data.

## Organization and customization

`src/constants/config.js` centralizes project identity. `src/styles.css` defines reusable light/dark CSS variables and Tailwind tokens. `src/data/mock.js` holds sample records and quantity/status helpers. `src/hooks/useStore.jsx` owns local persistence and allocations. Reusable UI lives in `src/components`, the shared shell in `src/layouts`, and role pages in `src/pages`. Allocation checks reject invalid quantities and ineligible alternative routes.

**Phase 2:** Backend, database, real AI prediction, real quality assessment, and real matching services will be integrated in Phase 2. They are not implemented now. The central state layer and plain records provide a boundary for a future FastAPI + PostgreSQL integration.
