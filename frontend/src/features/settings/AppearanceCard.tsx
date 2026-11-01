import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { SegmentedControl } from "../../components/ui/SegmentedControl";
import { useTheme } from "../../lib/theme";

const OPTIONS = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
] as const;

/**
 * Saves on change with no button: there is nothing to validate and nothing to
 * send to the server — the preference is per-viewer, in localStorage. The
 * blocking script in index.html reads it back before first paint, which is why
 * there is no flash on reload and why nothing here duplicates that logic.
 */
export function AppearanceCard() {
  const { pref, setPref } = useTheme();

  return (
    <Card>
      <CardHeader
        title="Appearance"
        description="Applies to this device only, not to other people using the app."
      />
      <CardBody>
        <SegmentedControl
          label="Theme"
          value={pref}
          options={OPTIONS}
          fullWidth
          onChange={(value) => {
            setPref(value);
          }}
        />
      </CardBody>
    </Card>
  );
}
