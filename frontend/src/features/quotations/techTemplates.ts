import type { TechRow } from "../../api/types";

/**
 * Ready-made rows for the technical offer sheet, after the offers the
 * customers already receive (ESQP 26-296 end suction, 26-317 borewell).
 * Picking one fills the rows; any row can then be renamed, added or removed
 * for that quotation.
 */
const DUTY = "Duty Conditions";
const MOC = "Material Of Construction";
const MOTOR = "Motor Data";

export const TECH_TEMPLATES: { name: string; rows: TechRow[] }[] = [
  {
    name: "End suction pump",
    rows: [
      ...[
        "Liquid Handled",
        "Sp. Gravity",
        "Capacity (m³/hr)",
        "Total Head (m)",
        "Suc x Del size (mm)",
        "Efficiency",
        "Shaft Sealing",
        "Speed (rpm)",
        "NPSH R (m)",
        "Impeller type",
        "Shut Off head (m)",
        "BkW",
        "Pump type",
      ].map((label) => ({ section: DUTY, label })),
      ...["Volute Casing", "Shaft", "Impeller"].map((label) => ({ section: MOC, label })),
      ...["kW / IEC Frame Size", "Make"].map((label) => ({ section: MOTOR, label })),
    ],
  },
  {
    name: "Borewell submersible",
    rows: [
      ...[
        "Liquid Handled",
        "Sp. Gravity",
        "Capacity (m³/hr)",
        "Total Head (m)",
        "Del size (mm)",
        "Shaft Sealing",
        "Speed (rpm)",
        "Impeller type",
        "No of Stage",
        "Shut Off head (m)",
        "Pump type",
      ].map((label) => ({ section: DUTY, label })),
      ...["Stage Casing", "Shaft", "Impeller", "Suction Housing", "NRV Housing"].map((label) => ({
        section: MOC,
        label,
      })),
      ...["Motor Type", "Motor", "Motor kW", "Voltage", "Cable Size"].map((label) => ({
        section: MOTOR,
        label,
      })),
    ],
  },
];
