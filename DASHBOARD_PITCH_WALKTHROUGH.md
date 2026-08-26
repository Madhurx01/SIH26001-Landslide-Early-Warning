# 🖥️ AAPTIRAKSHAK — Live Dashboard Pitch & Feature Walkthrough
## Step-by-Step Clickable Presentation Guide for Judges (3-Minute Flow)

---

```text
 ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                   DASHBOARD DEMONSTRATION ROADMAP                           │
 ├─────────────────────────┬───────────────────────────┬───────────────────────────────────────┤
 │ PHASE 1: COMMAND HEADER │ PHASE 2: SATELLITE & MAP  │ PHASE 3: TREESHAP & LIFELINES         │
 │ • Live/Disaster Toggle  │ • 2,984 Hex Spatial Grid  │ • XAI Factor Decomposition            │
 │ • Hourly IST Timestamp  │ • NDMA 4-Color Alerts     │ • Highway Inspector (NH-10)           │
 ├─────────────────────────┼───────────────────────────┼───────────────────────────────────────┤
 │ PHASE 4: RBAC SECURITY  │ PHASE 5: LIVE MOBILE SYNC │ PHASE 6: TACTICAL DISPATCH            │
 │ • 3 Personas (JWT)      │ • Camera + GPS Telemetry  │ • BRO Escalation                      │
 │ • IP Control Room Guard │ • Firebase Cloud < 2s     │ • SDRF Evacuation Queue               │
 └─────────────────────────┴───────────────────────────┴───────────────────────────────────────┘
```

---

# ⏱️ PHASE 1: The Overview & Live Satellite Radar (0:00 - 0:30)

### 🖱️ Screen Action:
* Keep your dashboard on **[http://localhost:5173/](http://localhost:5173/)** in **Live Mode** (`🛰️ Live Satellite Radar`).
* Point with your cursor to the top banner and header.

### 🗣️ What to Say:
> *"Respected Judges, welcome to the **AAPTIRAKSHAK Tactical Disaster Command Dashboard** for Sikkim.
> 
> Notice our top navigation bar: our backend runs an automated serverless ML worker that queries live **Open-Meteo and NASA satellite radars** across Gangtok, Mangan, Namchi, and Geyzing, updating our risk layers hourly in Indian Standard Time with **zero manual intervention**.
> 
> Right now, under normal weather conditions, you see green baseline conditions across Sikkim with $15\text{ mm}$ of average rain and $40\%$ soil saturation."*

---

# ⏱️ PHASE 2: The Disaster Storm Toggle & 2,984-Cell GIS Map (0:30 - 1:00)

### 🖱️ Screen Action:
* Click the red button: **`🚨 Simulate Disaster Storm (19 Oct)`**.
* Watch the entire Leaflet GIS map dynamically light up with red and orange risk hexagons.
* Zoom in slightly on the **Teesta River corridor / NH-10 corridor**.

### 🗣️ What to Say:
> *"Now, watch what happens when severe weather strikes. With one click, I am switching to our **Historical Disaster Simulation Mode**, recreating the catastrophic October 19, 2021 storm.
> 
> In **$36\text{ milliseconds}$**, our Cost-Sensitive XGBoost model evaluates all **2,984 spatial cells** covering $7,096\text{ km}^2$. 
> 
> Notice how the map dynamically lights up **1,793 Red Alert cells** along the high-risk Teesta river cutting and NH-10 lifeline. The KPI summary cards immediately update to reflect 5 endangered highway arteries and 7 vulnerable settlements."*

---

# ⏱️ PHASE 3: TreeSHAP Explainable AI & Highway Inspector (1:00 - 1:45)

### 🖱️ Screen Action:
1. Click on a **Red Hexagon Cell** on the map (e.g. `SKM_04329` along the North Sikkim Highway).
2. Point to the **Selected Cell Inspector Panel** on the right, highlighting the **SHAP Diverging Factor Bars**.
3. Scroll down and click **"Inspect"** on **NH-10 (Siliguri - Gangtok Lifeline)** in the **Highway Lifeline Inspector Panel**.

### 🗣️ What to Say:
> *"In life-safety operations, black-box AI is unacceptable. When I click on cell **SKM_04329**, our **TreeSHAP Explainability Engine** mathematically proves why this cell triggered a $92\%$ Red Warning:
> * **$+41\%$ risk contribution** from $166\text{ mm}$ 3-day rainfall accumulation.
> * **$+28\%$ contribution** from $89\%$ soil moisture saturation.
> * **$+14\%$ contribution** from steep road toe excavation.
> * **$-3\%$ buffer** from canopy vegetation.
> 
> Scrolling down to our **Highway Lifeline Inspector**, commanders can inspect real-time risk profiles across NH-10, the North Sikkim Highway, and the Chungthang-Lachen/Lachung corridor, preemptively identifying critical choke points before debris blocks military or tourist transit."*

---

# ⏱️ PHASE 4: Enterprise RBAC & State-Grade Cybersecurity (1:45 - 2:15)

### 🖱️ Screen Action:
1. Click on the **User Badge** at the top right (`Col. D. S. Rawat`).
2. Point to your authorized IP badge (`👑 MASTER ADMIN IP AUTHORIZED`).
3. Click on the **`Citizen / Traveler (Viewer)`** role card to switch roles.
4. Show how the dashboard instantly transitions into **Public Safety Mode** (the military tactical queue disappears and is replaced by **Citizen Safety Advisories & Helplines 1070/112**).

### 🗣️ What to Say:
> *"In a state crisis, access security is paramount. AAPTIRAKSHAK implements **Role-Based Access Control secured by cryptographic JWT tokens**:
> 
> 1. **Disaster Commander (`admin`):** Full tactical dispatch, road closure, and siren authority.
> 2. **GIS Scientist (`analyst`):** Deep research analytics and TreeSHAP diagnostics.
> 3. **Public Citizen (`viewer`):** Restricted to public safety advisories and emergency helplines.
> 
> Furthermore, access to the Disaster Commander role is **IP-Gated**. Any unauthorized outside IP is locked out of tactical commands unless verified via our master security passcode."*

---

# ⏱️ PHASE 5: Live Mobile Citizen Reporting & Cloud Sync (2:15 - 3:00)

### 🖱️ Screen Action:
1. Switch back to **`Admin`** role on your laptop and scroll to the **Citizen Incident Verification Queue** (pointing out the `🟢 Firebase Realtime Cloud Sync Active` badge).
2. On your phone (or a secondary window), open the report modal $\rightarrow$ click **"Auto-Detect GPS"** $\rightarrow$ take a camera photo $\rightarrow$ click **"Submit Report"**.
3. Watch the report **instantly pop up on the laptop screen in $< 2\text{ seconds}$**.
4. Click **"✅ Verify & Alert BRO"** on the laptop.

### 🗣️ What to Say:
> *"Finally, we bridge satellite models with ground reality through **Crowd-Sourced Incident Telemetry**.
> 
> On this mobile phone, a citizen spots active rock tumbling along NH-10. The phone auto-detects GPS, snaps a live camera photo, compresses it in $10\text{ ms}$ using client-side canvas downscaling to just $35\text{ KB}$, and submits.
> 
> Watch my laptop screen: **within 2 seconds, without any page refresh**, the report pops up live in our **Citizen Incident Verification Queue** with the exact coordinates and evidence photo!
> 
> As the State Disaster Commander, I inspect the photo and click **'Verify & Alert BRO'**—instantly mobilizing Border Roads Organisation road-clearing machinery and broadcasting public safety alerts.
> 
> AAPTIRAKSHAK is complete, zero-sensor hardware, production-ready, and built to protect the Himalayas. Thank you!"*

---

# 📊 Quick Reference Feature Matrix:

| Feature / Panel | What It Does | Who Can Use It |
| :--- | :--- | :---: |
| **🛰️ Live / Storm Toggle** | Switches between live Open-Meteo satellite feed and 19 Oct 2021 disaster storm. | All Roles |
| **⏱️ 2021 Monsoon Time Machine** | Interactive 5-milestone timeline slider scrubbing the 2021 monsoon season. | Analyst & Admin |
| **🗺️ 2,984-Cell GIS Map** | High-resolution $30\text{m}$ grid with NDMA 4-color risk overlays and road networks. | All Roles |
| **🔬 TreeSHAP Cell Inspector** | Explains the exact mathematical percentage contribution of each physical factor. | Analyst & Admin |
| **🛣️ Highway Lifeline Inspector** | Real-time transit hazard analysis for NH-10, North Sikkim Highway, Lachen/Lachung. | All Roles |
| **🛡️ Verification Queue** | Live cloud stream of citizen mobile photos and GPS for BRO/SDRF escalation. | **Admin Only** |
| **🚨 Tactical Emergency Action Queue** | Prioritized military & SDRF rescue/evacuation recommendations. | **Admin Only** |
| **🔑 Master Admin IP Guard** | Cryptographically restricts commander privileges to authorized Control Room IPs. | Security Layer |
| **📱 Mobile PWA Citizen Reporter** | Live camera capture + GPS auto-detect + $35\text{ KB}$ canvas compression. | Public Citizens |
