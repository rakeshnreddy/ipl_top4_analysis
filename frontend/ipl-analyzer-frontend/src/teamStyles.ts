// Team Names and Styles

export interface TeamStyle {
  bg: string;
  text: string;
  accent?: string; // Add this line
}

export interface TeamStyles {
  [key: string]: TeamStyle;
}

export interface TeamNames {
  [key: string]: string;
}

export const team_full_names: TeamNames = {
  Rajasthan: "Rajasthan Royals",
  Kolkata: "Kolkata Knight Riders",
  Lucknow: "Lucknow Super Giants",
  Hyderabad: "Sunrisers Hyderabad",
  Chennai: "Chennai Super Kings",
  Delhi: "Delhi Capitals",
  Punjab: "Punjab Kings",
  Gujarat: "Gujarat Titans",
  Mumbai: "Mumbai Indians",
  Bangalore: "Royal Challengers Bangalore",
};

export const team_short_names: TeamNames = {
  Rajasthan: "RR",
  Kolkata: "KKR",
  Lucknow: "LSG",
  Hyderabad: "SRH",
  Chennai: "CSK",
  Delhi: "DC",
  Punjab: "PBKS",
  Gujarat: "GT",
  Mumbai: "MI",
  Bangalore: "RCB",
};

export const team_styles: TeamStyles = {
  // Updated with official hex codes and contrast-safe text colors
  Mumbai: { bg: "#004B8D", text: "#FFFFFF" },
  Chennai: { bg: "#F9CD05", text: "#000000" },
  Bangalore: { bg: "#EC1C24", text: "#FFFFFF" },
  Kolkata: { bg: "#3A225D", text: "#FFFFFF" },
  Hyderabad: { bg: "#FEDC32", text: "#000000" },
  Delhi: { bg: "#2561AE", text: "#FFFFFF" },
  Punjab: { bg: "#ED1D24", text: "#FFFFFF" },
  Rajasthan: { bg: "#254AA5", text: "#FFFFFF" },
  Gujarat: { bg: "#0A1C34", text: "#FFFFFF" },
  Lucknow: { bg: "#0057E2", text: "#FFFFFF" },
};

// Reverse mapping from FULL name to key
export const full_name_key_mapping: TeamNames = Object.fromEntries(
  Object.entries(team_full_names).map(([key, value]) => [value, key])
);
