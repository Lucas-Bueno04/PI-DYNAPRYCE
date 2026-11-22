import { createTheme } from "@mantine/core";

export const tema = createTheme({
  primaryColor: "indigo",
  defaultRadius: "md",
  fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
  headings: { fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif", fontWeight: "650" },
  components: {
    Card: { defaultProps: { withBorder: true, radius: "lg", padding: "lg" } },
    Table: { defaultProps: { highlightOnHover: true, verticalSpacing: "sm" } },
  },
});
