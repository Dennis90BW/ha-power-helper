/*
 * powerHELPER – Leistungsfluss-Karte für Home Assistant
 *
 * Zeigt die von powerHELPER berechneten Leistungsflüsse zwischen PV, Netz,
 * Akku und Haus – angelehnt an die Energieverteilung des Energie-Dashboards.
 * Drei Darstellungen: klassisch, rund, Dreieck.
 *
 * Wird von der Integration automatisch im Frontend registriert.
 */
(() => {
  const CARD_TYPE = "power-helper-card";
  const DOMAIN = "power_helper";
  const MAIN_MODEL = "powerHELPER";
  const ACTIVE_THRESHOLD = 0.5; // W – darunter gilt ein Fluss als 0

  // ---------------------------------------------------------------------------
  // Texte
  // ---------------------------------------------------------------------------
  const I18N = {
    de: {
      name: "powerHELPER Leistungsfluss",
      description: "Leistungsflüsse zwischen PV, Netz, Akku und Haus",
      pv: "PV",
      grid: "Netz",
      battery: "Akku",
      home: "Haus",
      no_device: "Bitte im Karten-Editor ein powerHELPER-Gerät auswählen.",
      no_entities: "Für dieses Gerät wurden keine powerHELPER-Sensoren gefunden.",
      link_energy: "Energie-Dashboard aufrufen",
      link_power_helper: "powerHELPER aufrufen",
      editor: {
        device_id: "powerHELPER-Gerät",
        title: "Titel (optional)",
        layout: "Darstellung",
        show_zero_flows: "0 W an Linien anzeigen",
        show_zero_node_values: "0 W in Kreisen anzeigen",
        link_energy_dashboard: "Link zum Energie-Dashboard",
        link_power_helper: "Link zum powerHELPER",
        links: "Links",
      },
      layouts: { classic: "Klassisch", round: "Rund", triangle: "Dreieck" },
    },
    en: {
      name: "powerHELPER Power Flow",
      description: "Power flows between PV, grid, battery and home",
      pv: "PV",
      grid: "Grid",
      battery: "Battery",
      home: "Home",
      no_device: "Please select a powerHELPER device in the card editor.",
      no_entities: "No powerHELPER sensors were found for this device.",
      link_energy: "Go to the energy dashboard",
      link_power_helper: "Go to powerHELPER",
      editor: {
        device_id: "powerHELPER device",
        title: "Title (optional)",
        layout: "Layout",
        show_zero_flows: "Show 0 W on lines",
        show_zero_node_values: "Show 0 W in circles",
        link_energy_dashboard: "Link to the energy dashboard",
        link_power_helper: "Link to powerHELPER",
        links: "Links",
      },
      layouts: { classic: "Classic", round: "Round", triangle: "Triangle" },
    },
  };

  function languageOf(hass) {
    const raw =
      (hass && ((hass.locale && hass.locale.language) || hass.language)) ||
      (typeof document !== "undefined" && document.documentElement && document.documentElement.lang) ||
      "en";
    const short = String(raw).slice(0, 2).toLowerCase();
    return I18N[short] ? short : "en";
  }

  function globalHass() {
    if (typeof document === "undefined") return undefined;
    const ha = document.querySelector("home-assistant");
    return ha && ha.hass;
  }

  // ---------------------------------------------------------------------------
  // Farben (Variablen des Energie-Dashboards mit Rückfallwerten)
  // ---------------------------------------------------------------------------
  const COLORS = {
    solar: "var(--energy-solar-color, #ff9800)",
    grid_in: "var(--energy-grid-consumption-color, #488fc2)",
    grid_out: "var(--energy-grid-return-color, #8353d1)",
    bat_in: "var(--energy-battery-in-color, #f06292)",
    bat_out: "var(--energy-battery-out-color, #4db6ac)",
    home: "var(--primary-color, #03a9f4)",
    neutral: "var(--primary-text-color, #e1e1e1)",
  };

  const ICONS = {
    pv: "mdi:solar-power",
    grid: "mdi:transmission-tower",
    battery: "mdi:battery-high",
    home: "mdi:home",
  };

  // ---------------------------------------------------------------------------
  // Werte
  // ---------------------------------------------------------------------------

  /** Sensor-Schlüssel (translation_key) der Leistungsflüsse */
  const FLOW_KEYS = {
    pv_home: "pv_zu_haus",
    pv_bat: "pv_zu_akku",
    pv_grid: "pv_zu_netz",
    grid_home: "netz_zu_haus",
    grid_bat: "netz_zu_akku",
    bat_grid: "akku_zu_netz",
    bat_home: "akku_zu_haus",
  };

  /** Sensoren, die beim Klick auf einen Kreis geöffnet werden (erster vorhandener) */
  const MORE_INFO = {
    pv: ["pv_leistung", "pv_zu_haus"],
    grid: ["netz_leistung", "netz_bezug", "netz_zu_haus"],
    battery: ["akku_leistung", "akku_laden", "akku_zu_haus"],
    home: ["haus"],
  };

  /** Knotenwerte aus den Flüssen berechnen – so passen Kreise und Linien immer zusammen. */
  function computeValues(raw) {
    const v = (key) => {
      const x = raw[key];
      return typeof x === "number" && isFinite(x) ? Math.max(x, 0) : 0;
    };
    const f = {};
    for (const [id, key] of Object.entries(FLOW_KEYS)) f[id] = v(key);
    return {
      flows: f,
      nodes: {
        pv: f.pv_home + f.pv_bat + f.pv_grid,
        grid_in: f.grid_home + f.grid_bat,
        grid_out: f.pv_grid + f.bat_grid,
        bat_in: f.pv_bat + f.grid_bat,
        bat_out: f.bat_home + f.bat_grid,
        home: f.pv_home + f.bat_home + f.grid_home,
      },
    };
  }

  function formatPower(watt, locale) {
    if (watt == null || !isFinite(watt)) return "—";
    const abs = Math.abs(watt);
    if (Math.round(abs) < 1000) {
      return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(watt)} W`;
    }
    const kw = new Intl.NumberFormat(locale, {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }).format(watt / 1000);
    return `${kw} kW`;
  }

  /** Dauer eines Punkt-Umlaufs: mehr Leistung = schneller (in Stufen, damit die Animation nicht ständig neu startet) */
  function dotDuration(watt) {
    const steps = [
      [5000, 1.5],
      [2000, 2],
      [1000, 2.5],
      [500, 3],
      [100, 4],
    ];
    for (const [min, dur] of steps) if (watt >= min) return dur;
    return 5;
  }

  // ---------------------------------------------------------------------------
  // Geometrie
  // ---------------------------------------------------------------------------
  const line = (a, b) => ({ type: "line", a, b });
  const arc = (c, r, a0, a1) => ({ type: "arc", c, r, a0, a1 });
  /** Pfad aus Teilstücken: ["L", [x, y]] oder ["C", c1, c2, [x, y]] */
  const poly = (start, ...segs) => ({ type: "poly", start, segs });

  const round1 = (n) => Math.round(n * 10) / 10;
  const pt = (p) => `${round1(p[0])},${round1(p[1])}`;

  function polar(c, r, deg) {
    const t = (deg * Math.PI) / 180;
    return [c[0] + r * Math.cos(t), c[1] + r * Math.sin(t)];
  }

  function cubicAt(p0, p1, p2, p3, t) {
    const u = 1 - t;
    const w = [u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t];
    return [0, 1].map((i) => w[0] * p0[i] + w[1] * p1[i] + w[2] * p2[i] + w[3] * p3[i]);
  }

  function pathD(g) {
    if (g.type === "line") return `M${pt(g.a)} L${pt(g.b)}`;
    if (g.type === "poly") {
      const parts = g.segs.map((sg) =>
        sg[0] === "L" ? `L${pt(sg[1])}` : `C${pt(sg[1])} ${pt(sg[2])} ${pt(sg[3])}`
      );
      return `M${pt(g.start)} ${parts.join(" ")}`;
    }
    const st = polar(g.c, g.r, g.a0);
    const e = polar(g.c, g.r, g.a1);
    const delta = g.a1 - g.a0;
    const large = Math.abs(delta) > 180 ? 1 : 0;
    const sweep = delta > 0 ? 1 : 0;
    return `M${pt(st)} A${round1(g.r)},${round1(g.r)} 0 ${large} ${sweep} ${pt(e)}`;
  }

  /** Punkt bei Anteil t (0..1) der Pfadlänge */
  function pointAt(g, t) {
    if (g.type === "line") return [g.a[0] + (g.b[0] - g.a[0]) * t, g.a[1] + (g.b[1] - g.a[1]) * t];
    if (g.type === "arc") return polar(g.c, g.r, g.a0 + (g.a1 - g.a0) * t);
    // poly: als Polylinie annähern und nach Länge interpolieren
    const pts = [g.start];
    let cur = g.start;
    for (const sg of g.segs) {
      if (sg[0] === "L") {
        pts.push(sg[1]);
        cur = sg[1];
      } else {
        for (let i = 1; i <= 16; i++) pts.push(cubicAt(cur, sg[1], sg[2], sg[3], i / 16));
        cur = sg[3];
      }
    }
    const lens = [0];
    for (let i = 1; i < pts.length; i++) {
      lens.push(lens[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
    }
    const target = t * lens[lens.length - 1];
    for (let i = 1; i < pts.length; i++) {
      if (lens[i] >= target) {
        const f = (target - lens[i - 1]) / (lens[i] - lens[i - 1] || 1);
        return [pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * f, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * f];
      }
    }
    return pts[pts.length - 1];
  }

  /** Position der Leistungszahl: feste Koordinate (at) oder Anteil t auf der Linie */
  function labelPoint(flow) {
    return flow.at ? flow.at : pointAt(flow.g, flow.t);
  }

  // Maße wie die Energieverteilung von Home Assistant: Kreise immer 80 px, Schrift 12 px.
  // Nur die Abstände und damit die Linien passen sich der Kartenbreite an.
  const R = 40;
  const RADIUS = { pv: R, grid: R, battery: R, home: R };
  const MIN_WIDTH = 300;
  const MAX_WIDTH = 500;
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  /** Randpunkt eines Kreises (Radius R) bei gegebenem x bzw. y */
  const edgeY = (c, x, sign) => c[1] + sign * Math.sqrt(Math.max(R * R - (x - c[0]) ** 2, 0));
  const edgeX = (c, y, sign) => c[0] + sign * Math.sqrt(Math.max(R * R - (y - c[1]) ** 2, 0));

  const NAMES_CLASSIC = { pv: "above", grid: "below", battery: "below", home: "below" };
  const NAMES_STAR = { pv: "above", grid: "below", battery: "below", home: null };

  /**
   * Klassisch wie die Energieverteilung: Netz links am Rand, Haus rechts am Rand,
   * PV und Akku in der Mitte. Linien laufen senkrecht aus den Kreisen, biegen in
   * einem Bogen ab und gehen waagerecht weiter.
   */
  function classicLayout(width) {
    const W = clamp(width, MIN_WIDTH, MAX_WIDTH);
    const cx = W / 2;
    const pv = [cx, 60];
    const grid = [42, 168];
    const home = [W - 42, 168];
    const battery = [cx, 282];
    const yTop = 150; // waagerechte Linien über der Mitte
    const yBot = 186; // waagerechte Linien unter der Mitte

    // Platz zwischen Netz-Rand und Mitte bestimmt Versatz und Bogenradius
    const space = cx - (grid[0] + R);
    const d = clamp(space * 0.15, 12, 25);
    const rad = clamp(space * 0.25, 14, 40);
    const k = rad * 0.552; // Kontrollpunkt-Abstand für einen Viertelkreis

    const pvL = cx - d;
    const pvR = cx + d;
    const pvY = edgeY(pv, pvR, 1);
    const batY = edgeY(battery, pvR, -1);
    const gx = edgeX(grid, yTop, 1);
    const hx = edgeX(home, yTop, -1);
    const leftEnd = pvL - rad;
    const rightStart = pvR + rad;

    return {
      w: W,
      h: 348,
      radius: RADIUS,
      nodes: { pv, grid, home, battery },
      names: NAMES_CLASSIC,
      flows: {
        pv_home: {
          g: poly([pvR, pvY], ["L", [pvR, yTop - rad]], ["C", [pvR, yTop - rad + k], [rightStart - k, yTop], [rightStart, yTop]], ["L", [hx, yTop]]),
          at: [(rightStart + hx) / 2, yTop],
        },
        pv_grid: {
          g: poly([pvL, pvY], ["L", [pvL, yTop - rad]], ["C", [pvL, yTop - rad + k], [leftEnd + k, yTop], [leftEnd, yTop]], ["L", [gx, yTop]]),
          at: [(leftEnd + gx) / 2, yTop],
        },
        pv_bat: { g: line([cx, pv[1] + R], [cx, battery[1] - R]), at: [cx, 207] },
        grid_home: {
          g: line([grid[0] + R, grid[1]], [home[0] - R, home[1]]),
          at: [Math.max(cx - d - 40, gx + 22), grid[1]],
        },
        grid_bat: {
          g: poly([gx, yBot], ["L", [leftEnd, yBot]], ["C", [leftEnd + k, yBot], [pvL, yBot + rad - k], [pvL, yBot + rad]], ["L", [pvL, batY]]),
          at: [(leftEnd + gx) / 2, yBot],
        },
        bat_home: {
          g: poly([pvR, batY], ["L", [pvR, yBot + rad]], ["C", [pvR, yBot + rad - k], [rightStart - k, yBot], [rightStart, yBot]], ["L", [hx, yBot]]),
          at: [(rightStart + hx) / 2, yBot],
        },
      },
    };
  }

  /** Rund/Dreieck: Haus in der Mitte, PV oben, Netz links unten, Akku rechts unten */
  function starNodes(width) {
    const W = clamp(width, MIN_WIDTH, MAX_WIDTH);
    const SR = Math.min(160, (W / 2 - 44) / Math.cos(Math.PI / 6));
    const c = [W / 2, 60 + SR];
    return {
      W,
      SR,
      c,
      nodes: { pv: polar(c, SR, -90), grid: polar(c, SR, 150), battery: polar(c, SR, 30), home: c },
    };
  }

  function roundLayout(width) {
    const { W, SR, c, nodes } = starNodes(width);
    return {
      w: W,
      h: Math.ceil(c[1] + SR + 16),
      radius: RADIUS,
      nodes,
      names: NAMES_STAR,
      flows: {
        pv_home: { g: line(nodes.pv, nodes.home), t: 0.5 },
        grid_home: { g: line(nodes.grid, nodes.home), t: 0.5 },
        bat_home: { g: line(nodes.battery, nodes.home), t: 0.5 },
        pv_grid: { g: arc(c, SR, -90, -210), t: 0.5 },
        pv_bat: { g: arc(c, SR, -90, 30), t: 0.5 },
        grid_bat: { g: arc(c, SR, 150, 30), t: 0.5 },
      },
    };
  }

  function triangleLayout(width) {
    const { W, SR, c, nodes } = starNodes(width);
    return {
      w: W,
      h: Math.ceil(c[1] + SR / 2 + 66),
      radius: RADIUS,
      nodes,
      names: NAMES_STAR,
      flows: {
        pv_home: { g: line(nodes.pv, nodes.home), t: 0.5 },
        grid_home: { g: line(nodes.grid, nodes.home), t: 0.5 },
        bat_home: { g: line(nodes.battery, nodes.home), t: 0.5 },
        pv_grid: { g: line(nodes.pv, nodes.grid), t: 0.5 },
        pv_bat: { g: line(nodes.pv, nodes.battery), t: 0.5 },
        grid_bat: { g: line(nodes.grid, nodes.battery), t: 0.5 },
      },
    };
  }

  /** Darstellungen: Funktion Breite (px) → Geometrie in Pixeln */
  const LAYOUTS = { classic: classicLayout, round: roundLayout, triangle: triangleLayout };

  /**
   * Linien der Karte. grid_bat ist eine gemeinsame Linie für Netz → Akku und
   * Akku → Netz (nach der Verrechnung ist höchstens eine Richtung aktiv).
   */
  const LINES = [
    { id: "pv_home", needs: ["pv"], color: () => COLORS.solar },
    { id: "pv_bat", needs: ["pv", "battery"], color: () => COLORS.bat_in },
    { id: "pv_grid", needs: ["pv"], color: () => COLORS.grid_out },
    { id: "grid_home", needs: [], color: () => COLORS.grid_in },
    { id: "bat_home", needs: ["battery"], color: () => COLORS.bat_out },
    {
      id: "grid_bat",
      needs: ["battery"],
      color: () => COLORS.neutral,
    },
  ];

  /** Wert und Richtung einer Linie (reverse = entgegen der Geometrie) */
  function lineFlow(id, flows) {
    if (id === "grid_bat") {
      if (flows.bat_grid > flows.grid_bat) return { value: flows.bat_grid, reverse: true };
      return { value: flows.grid_bat, reverse: false };
    }
    return { value: flows[id], reverse: false };
  }

  // ---------------------------------------------------------------------------
  // Karte
  // ---------------------------------------------------------------------------
  const STYLE = `
    :host { display: block; }
    ha-card { height: 100%; box-sizing: border-box; display: flex; flex-direction: column; }
    .content { padding: 16px; flex: 1; }
    ha-card.has-title .content { padding-top: 0; }
    .content { overflow: hidden; }
    .wrap { position: relative; margin: 0 auto; }
    svg { display: block; overflow: visible; }
    .flow { fill: none; stroke-width: 2; transition: stroke 0.3s; }
    .footer {
      border-top: 1px solid var(--divider-color, rgba(127, 127, 127, 0.3));
      padding: 4px 8px; display: flex; flex-wrap: wrap; gap: 4px;
    }
    .footer a {
      color: var(--primary-color); text-decoration: none; font-weight: 500;
      font-size: 14px; padding: 8px; border-radius: 4px; cursor: pointer;
    }
    .footer a:hover { background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.08); }
    .node-bg { fill: var(--card-background-color, var(--ha-card-background, #fff)); stroke-width: 2; }
    .ring { fill: none; stroke-width: 4; }
    .label {
      font-size: 12px; font-family: var(--ha-font-family-body, Roboto, sans-serif);
      text-anchor: middle; dominant-baseline: central;
      paint-order: stroke; stroke: var(--card-background-color, var(--ha-card-background, #fff));
      stroke-width: 6px; stroke-linejoin: round;
    }
    .name {
      font-size: 12px; font-family: var(--ha-font-family-body, Roboto, sans-serif);
      fill: var(--secondary-text-color); text-anchor: middle;
    }
    .node {
      position: absolute; box-sizing: border-box; border-radius: 50%;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      color: var(--primary-text-color); line-height: 1.15; text-align: center;
    }
    .node.clickable { cursor: pointer; }
    .node ha-icon { --mdc-icon-size: 24px; color: var(--primary-text-color); margin-bottom: 2px; }
    .node .v { font-size: 12px; line-height: 14px; white-space: nowrap; display: flex; align-items: center; justify-content: center; }
    .node .v ha-icon { --mdc-icon-size: 12px; color: inherit; margin: 0 1px 0 0; }
    .msg { padding: 16px; color: var(--secondary-text-color); }
  `;

  class PowerHelperCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._structureKey = null;
      this._valueKey = null;
      this._els = null;
      this._width = MAX_WIDTH;
      this._content = null;
      this._resizeObserver = null;
    }

    connectedCallback() {
      if (this._resizeObserver && this._content) this._resizeObserver.observe(this._content);
    }

    disconnectedCallback() {
      if (this._resizeObserver) this._resizeObserver.disconnect();
    }

    /** Verfügbare Breite beobachten – bei Änderung Geometrie neu berechnen */
    _observeWidth(el) {
      if (typeof ResizeObserver === "undefined") return;
      if (!this._resizeObserver) {
        this._resizeObserver = new ResizeObserver((entries) => {
          const w = Math.floor(entries[0].contentRect.width);
          if (w <= 0) return;
          const width = clamp(w, MIN_WIDTH, MAX_WIDTH);
          if (width !== this._width) {
            this._width = width;
            this._structureKey = null;
            this._render();
          }
        });
      }
      this._resizeObserver.disconnect();
      this._resizeObserver.observe(el);
      this._content = el;
    }

    static getStubConfig(hass) {
      const devices = Object.values((hass && hass.devices) || {});
      const main = devices.find((d) => d.model === MAIN_MODEL);
      return {
        device_id: main ? main.id : "",
        // Titel mit dem Gerätenamen vorausfüllen (vom Nutzer vergebener Name hat Vorrang)
        title: main ? main.name_by_user || main.name || "" : "",
        layout: "classic",
        show_zero_flows: false,
        show_zero_node_values: true,
        link_energy_dashboard: true,
        link_power_helper: false,
      };
    }

    static getConfigForm() {
      const t = I18N[languageOf(globalHass())];
      return {
        schema: [
          {
            name: "device_id",
            required: true,
            selector: { device: { filter: [{ integration: DOMAIN, model: MAIN_MODEL }] } },
          },
          { name: "title", selector: { text: {} } },
          {
            name: "layout",
            selector: {
              select: {
                mode: "box",
                options: ["classic", "round", "triangle"].map((v) => ({
                  value: v,
                  label: t.layouts[v],
                })),
              },
            },
          },
          // 0-W-Anzeige nebeneinander, die Links darunter in eigenen Zeilen
          {
            type: "grid",
            name: "",
            schema: [
              { name: "show_zero_flows", selector: { boolean: {} } },
              { name: "show_zero_node_values", selector: { boolean: {} } },
            ],
          },
          {
            type: "expandable",
            name: "",
            title: t.editor.links,
            icon: "mdi:link-variant",
            flatten: true,
            schema: [
              { name: "link_energy_dashboard", selector: { boolean: {} } },
              { name: "link_power_helper", selector: { boolean: {} } },
            ],
          },
        ],
        computeLabel: (schema) => t.editor[schema.name],
      };
    }

    setConfig(config) {
      if (!config) throw new Error("Invalid configuration");
      const layout = LAYOUTS[config.layout] ? config.layout : "classic";
      this._config = {
        show_zero_flows: false,
        show_zero_node_values: true,
        link_energy_dashboard: true,
        link_power_helper: false,
        ...config,
        layout,
      };
      this._structureKey = null;
      this._valueKey = null;
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
      this._render();
    }

    getCardSize() {
      return 7;
    }

    getGridOptions() {
      return { columns: 12, min_columns: 6, rows: "auto" };
    }

    // ---------------- Daten ----------------

    _entityMap() {
      const map = {};
      const entities = (this._hass && this._hass.entities) || {};
      for (const [entityId, entry] of Object.entries(entities)) {
        if (
          entry.platform === DOMAIN &&
          entry.device_id === this._config.device_id &&
          entry.translation_key
        ) {
          map[entry.translation_key] = entityId;
        }
      }
      return map;
    }

    _rawValues(map) {
      const raw = {};
      for (const key of Object.values(FLOW_KEYS)) {
        const st = map[key] && this._hass.states[map[key]];
        raw[key] = st ? parseFloat(st.state) : null;
      }
      return raw;
    }

    // ---------------- Darstellung ----------------

    _render() {
      if (!this._config || !this._hass) return;
      const t = I18N[languageOf(this._hass)];

      if (!this._config.device_id) return this._message(t.no_device);
      const map = this._entityMap();
      if (!map.haus && !map.netz_zu_haus) return this._message(t.no_entities);

      const present = {
        pv: Boolean(map.pv_zu_haus),
        battery: Boolean(map.akku_zu_haus),
      };
      const structureKey = JSON.stringify([
        this._width,
        this._config.layout,
        this._config.show_zero_flows,
        this._config.link_energy_dashboard,
        this._config.link_power_helper,
        this._config.title || "",
        present,
        languageOf(this._hass),
      ]);
      if (structureKey !== this._structureKey) {
        this._build(present, t);
        this._structureKey = structureKey;
        this._valueKey = null;
      }
      this._entities = map;
      this._update(computeValues(this._rawValues(map)));
    }

    _message(text) {
      this._structureKey = null;
      this._els = null;
      this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card><div class="msg"></div></ha-card>`;
      this.shadowRoot.querySelector(".msg").textContent = text;
    }

    _build(present, t) {
      const L = LAYOUTS[this._config.layout](this._width);
      const nodes = ["pv", "grid", "home", "battery"].filter(
        (n) => n === "grid" || n === "home" || present[n]
      );
      const lines = LINES.filter((l) => l.needs.every((n) => present[n]));
      const svgNS = "http://www.w3.org/2000/svg";

      const root = this.shadowRoot;
      root.innerHTML = `<style>${STYLE}</style>`;
      const card = document.createElement("ha-card");
      if (this._config.title) {
        card.setAttribute("header", this._config.title);
        card.classList.add("has-title");
      }
      const wrap = document.createElement("div");
      wrap.className = "wrap";
      wrap.style.width = `${L.w}px`;
      wrap.style.height = `${L.h}px`;
      const svg = document.createElementNS(svgNS, "svg");
      svg.setAttribute("viewBox", `0 0 ${L.w} ${L.h}`);
      svg.setAttribute("width", L.w);
      svg.setAttribute("height", L.h);
      svg.setAttribute("role", "img");

      const mk = (tag, attrs = {}, parent = svg) => {
        const el = document.createElementNS(svgNS, tag);
        for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
        parent.appendChild(el);
        return el;
      };

      const gLines = mk("g");
      const gDots = mk("g");
      const gNodes = mk("g");
      const gLabels = mk("g");
      const gNames = mk("g");

      const els = { lines: {}, nodes: {}, ring: [], values: {} };

      for (const l of lines) {
        const geo = L.flows[l.id];
        const d = pathD(geo.g);
        const path = mk("path", { d, class: "flow" }, gLines);
        const dot = mk("circle", { r: 4 }, gDots);
        const anim = mk(
          "animateMotion",
          {
            dur: "4s",
            repeatCount: "indefinite",
            calcMode: "linear",
            keyPoints: "0;1",
            keyTimes: "0;1",
            path: d,
          },
          dot
        );
        const [lx, ly] = labelPoint(geo);
        const label = mk("text", { x: round1(lx), y: round1(ly), class: "label" }, gLabels);
        els.lines[l.id] = { def: l, path, dot, anim, label, dur: null, reverse: null };
      }

      for (const n of nodes) {
        const [cx, cy] = L.nodes[n];
        const r = L.radius[n];
        const bg = mk("circle", { cx: round1(cx), cy: round1(cy), r: r - 1, class: "node-bg" }, gNodes);
        if (n === "pv") bg.style.stroke = COLORS.solar;
        if (n === "grid") bg.style.stroke = COLORS.grid_in;
        if (n === "battery") bg.style.stroke = COLORS.bat_out;
        if (n === "home") {
          bg.style.stroke = "transparent";
          const circ = 2 * Math.PI * (r - 2);
          for (const color of [COLORS.home, COLORS.solar, COLORS.bat_out, COLORS.grid_in]) {
            const seg = mk(
              "circle",
              {
                cx: round1(cx),
                cy: round1(cy),
                r: r - 2,
                class: "ring",
                transform: `rotate(-90 ${round1(cx)} ${round1(cy)})`,
                "stroke-dasharray": `0 ${circ}`,
              },
              gNodes
            );
            seg.style.stroke = color;
            els.ring.push({ seg, circ });
          }
        }

        const pos = L.names[n];
        if (pos) {
          const name = mk(
            "text",
            {
              x: round1(cx),
              y: round1(pos === "above" ? cy - r - 8 : cy + r + 16),
              class: "name",
            },
            gNames
          );
          name.textContent = t[n];
        }

        const div = document.createElement("div");
        div.className = `node ${n}`;
        div.style.left = `${cx - r}px`;
        div.style.top = `${cy - r}px`;
        div.style.width = `${2 * r}px`;
        div.style.height = `${2 * r}px`;
        div.innerHTML = `<ha-icon icon="${ICONS[n]}"></ha-icon>`;
        div.addEventListener("click", () => this._moreInfo(n));
        // Zeilen im Kreis: [Wert, Farbe, Pfeil-Icon wie im Energie-Dashboard]
        const rows = {
          pv: [["pv", COLORS.solar, null]],
          grid: [
            ["grid_out", COLORS.grid_out, "mdi:arrow-left"],
            ["grid_in", COLORS.grid_in, "mdi:arrow-right"],
          ],
          battery: [
            ["bat_in", COLORS.bat_in, "mdi:arrow-down"],
            ["bat_out", COLORS.bat_out, "mdi:arrow-up"],
          ],
          home: [["home", "var(--primary-text-color)", null]],
        }[n];
        for (const [key, color, icon] of rows) {
          const v = document.createElement("div");
          v.className = "v";
          v.style.color = color;
          if (icon) {
            const arrow = document.createElement("ha-icon");
            arrow.setAttribute("icon", icon);
            v.appendChild(arrow);
          }
          const text = document.createElement("span");
          v.appendChild(text);
          div.appendChild(v);
          els.values[key] = { el: text, row: v, hideable: n === "grid" || n === "battery" };
        }
        els.nodes[n] = div;
        wrap.appendChild(div);
      }

      wrap.insertBefore(svg, wrap.firstChild);
      const content = document.createElement("div");
      content.className = "content";
      content.appendChild(wrap);
      card.appendChild(content);
      this._observeWidth(content);

      // Fußzeile mit Links (wie bei der Energieverteilung)
      const links = [];
      if (this._config.link_energy_dashboard) links.push([t.link_energy, "/energy"]);
      if (this._config.link_power_helper) {
        links.push([t.link_power_helper, `/config/integrations/integration/${DOMAIN}`]);
      }
      if (links.length) {
        const footer = document.createElement("div");
        footer.className = "footer";
        for (const [text, path] of links) {
          const a = document.createElement("a");
          a.href = path;
          a.textContent = text;
          a.addEventListener("click", (ev) => {
            ev.preventDefault();
            this._navigate(path);
          });
          footer.appendChild(a);
        }
        card.appendChild(footer);
      }
      root.appendChild(card);
      this._els = els;
      this._layout = L;
    }

    _update(values) {
      if (!this._els) return;
      const valueKey = JSON.stringify(values);
      if (valueKey === this._valueKey) return;
      this._valueKey = valueKey;

      const locale = (this._hass.locale && this._hass.locale.language) || this._hass.language;
      const fmt = (w) => formatPower(w, locale);
      const showZero = Boolean(this._config.show_zero_flows);

      // Linien: immer sichtbar wie im Energie-Dashboard; nur die Zahl verschwindet bei 0 W
      for (const item of Object.values(this._els.lines)) {
        const { value, reverse } = lineFlow(item.def.id, values.flows);
        const active = value > ACTIVE_THRESHOLD;
        const color = item.def.color(active && reverse);

        item.path.style.stroke = color;

        item.label.style.display = active || showZero ? "" : "none";
        item.label.style.fill = color;
        item.label.textContent = fmt(active ? value : 0);

        item.dot.style.display = active ? "" : "none";
        item.dot.style.fill = color;
        if (active) {
          const dur = dotDuration(value);
          if (dur !== item.dur) {
            item.anim.setAttribute("dur", `${dur}s`);
            item.dur = dur;
          }
          if (reverse !== item.reverse) {
            item.anim.setAttribute("keyPoints", reverse ? "1;0" : "0;1");
            item.reverse = reverse;
          }
        }
      }

      // Kreise
      const hideZeroInNodes = this._config.show_zero_node_values === false;
      for (const [key, { el, row, hideable }] of Object.entries(this._els.values)) {
        const value = values.nodes[key];
        el.textContent = fmt(value);
        row.style.display = hideable && hideZeroInNodes && !(value > ACTIVE_THRESHOLD) ? "none" : "";
      }
      for (const [n, div] of Object.entries(this._els.nodes)) {
        div.classList.toggle("clickable", Boolean(this._moreInfoEntity(n)));
      }

      // Ring ums Haus: Anteile von PV, Akku und Netz am Hausverbrauch
      if (this._els.ring.length) {
        const f = values.flows;
        const total = values.nodes.home;
        const parts = total > ACTIVE_THRESHOLD ? [0, f.pv_home, f.bat_home, f.grid_home] : [1, 0, 0, 0];
        const sum = parts.reduce((a, b) => a + b, 0) || 1;
        let offset = 0;
        this._els.ring.forEach(({ seg, circ }, i) => {
          const len = (parts[i] / sum) * circ;
          seg.setAttribute("stroke-dasharray", `${len} ${circ}`);
          seg.setAttribute("stroke-dashoffset", `${-offset}`);
          offset += len;
        });
      }
    }

    /** Navigation innerhalb der HA-App (ohne Neuladen) */
    _navigate(path) {
      window.history.pushState(null, "", path);
      window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
    }

    _moreInfoEntity(node) {
      const map = this._entities || {};
      for (const key of MORE_INFO[node] || []) {
        const id = map[key];
        if (id && this._hass.states[id]) return id;
      }
      return null;
    }

    _moreInfo(node) {
      const entityId = this._moreInfoEntity(node);
      if (!entityId) return;
      this.dispatchEvent(
        new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true })
      );
    }
  }

  // Für Tests: reine Hilfsfunktionen ohne DOM
  PowerHelperCard._internals = {
    I18N,
    LAYOUTS,
    LINES,
    computeValues,
    formatPower,
    dotDuration,
    lineFlow,
    pathD,
    pointAt,
    labelPoint,
  };

  if (!customElements.get(CARD_TYPE)) {
    customElements.define(CARD_TYPE, PowerHelperCard);
    const t = I18N[languageOf(globalHass())];
    window.customCards = window.customCards || [];
    window.customCards.push({
      type: CARD_TYPE,
      name: t.name,
      description: t.description,
      preview: true,
      documentationURL: "https://github.com/Dennis90BW/ha-power-helper",
    });
  }
})();
