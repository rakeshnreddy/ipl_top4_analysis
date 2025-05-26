// Team Names and Styles

export interface TeamStyle {
  bg: string;
  text: string;
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
  Rajasthan: { bg: "#FFC0CB", text: "#000000" }, // Pink bg, Black text
  Kolkata: { bg: "#3A225D", text: "#FFFFFF" }, // Purple bg, White text
  Lucknow: { bg: "#00AEEF", text: "#000000" }, // Light Blue bg, Black text
  Hyderabad: { bg: "#FF822A", text: "#000000" }, // Orange bg, Black text
  Chennai: { bg: "#FDB913", text: "#000000" }, // Yellow bg, Black text
  Delhi: { bg: "#004C93", text: "#FFFFFF" }, // Dark Blue bg, White text
  Punjab: { bg: "#AF0000", text: "#FFFFFF" }, // Darker Red bg, White text
  Gujarat: { bg: "#1C2C5B", text: "#FFFFFF" }, // Navy bg, White text
  Mumbai: { bg: "#006CB7", text: "#FFFFFF" }, // Blue bg, White text
  Bangalore: { bg: "#D11F2D", text: "#FFD700" }, // Red bg, Gold text
};

// Reverse mapping from FULL name to key
export const full_name_key_mapping: TeamNames = Object.fromEntries(
  Object.entries(team_full_names).map(([key, value]) => [value, key])
);
