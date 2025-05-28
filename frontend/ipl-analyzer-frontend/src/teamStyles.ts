// Team Names and Styles

export interface TeamStyle {
  bg: string; // Main background color or primary color for the team row/element
  text: string; // Text color for good contrast on 'bg'
  accent?: string; // Optional accent color for borders or highlights
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

//export const team_styles_original: TeamStyles = { // Keeping original as a reference if needed
//  CSK: { bg: '#FFD700', text: '#000080' }, // Gold, Navy Blue
//  MI: { bg: '#004BA0', text: '#FFFFFF' },  // Blue, White
//  RCB: { bg: '#EC1C24', text: '#000000' }, // Red, Black
//  KKR: { bg: '#3A225D', text: '#F2E205' }, // Purple, Gold/Yellow
//  SRH: { bg: '#FF822A', text: '#000000' }, // Orange, Black
//  PBKS: { bg: '#D71920', text: '#FFFFFF' },// Red, White
//  RR: { bg: '#FFC0CB', text: '#0000FF' },  // Pink, Blue
//  DC: { bg: '#00008B', text: '#FFFFFF' },  // Dark Blue, White
//  GT: { bg: '#1B2133', text: '#C4A758' },  // Dark Blue/Titanium, Gold
//  LSG: { bg: '#00B19D', text: '#FFFFFF' }, // Teal, White
//  DEFAULT: { bg: '#E0E0E0', text: '#000000' }, // Fallback/Default
//};

// New "Warm & Fuzzy" Theme with "Blended" (softer, harmonious) Colors
export const team_styles: TeamStyles = {
  Chennai: { bg: '#FDEFB2', text: '#6A4F00', accent: '#F9A825' },     // CSK
  Mumbai: { bg: '#B3E5FC', text: '#01579B', accent: '#29B6F6' },      // MI
  Bangalore: { bg: '#FFCDD2', text: '#B71C1C', accent: '#EF5350' },   // RCB
  Kolkata: { bg: '#E1BEE7', text: '#4A148C', accent: '#BA68C8' },     // KKR
  Hyderabad: { bg: '#FFCC80', text: '#E65100', accent: '#FFA726' },   // SRH
  Punjab: { bg: '#FFAB91', text: '#BF360C', accent: '#FF7043' },      // PBKS
  Rajasthan: { bg: '#D1C4E9', text: '#311B92', accent: '#9575CD' },   // RR
  Delhi: { bg: '#C5CAE9', text: '#1A237E', accent: '#7986CB' },       // DC
  Gujarat: { bg: '#CFD8DC', text: '#263238', accent: '#90A4AE' },     // GT
  Lucknow: { bg: '#C8E6C9', text: '#1B5E20', accent: '#81C784' },     // LSG
  DEFAULT: { bg: '#F5F5F5', text: '#424242', accent: '#BDBDBD' }, // Lighter default
 };


// Reverse mapping from FULL name to key
export const full_name_key_mapping: TeamNames = Object.fromEntries(
  Object.entries(team_full_names).map(([key, value]) => [value, key])
);
