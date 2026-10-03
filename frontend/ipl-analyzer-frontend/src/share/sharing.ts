import type { IplSeasonPayload } from '../data/iplData';
import {
  formatGeneratedDate,
  formatNrr,
  formatPercent,
  rankingSort,
  raceSnapshot,
  teamColor,
  top4Probability,
} from '../lib/standings';

export type ShareKind = 'instagram' | 'x' | 'whatsapp';

export function shareTexts(payload: IplSeasonPayload): Record<ShareKind, string> {
  const snapshot = raceSnapshot(payload);
  const topFour = snapshot.currentTopFour.map((team) => team.shortName).join(', ');
  const cutline = snapshot.cutlineTeam
    ? `${snapshot.cutlineTeam.shortName} (${formatPercent(top4Probability(payload, snapshot.cutlineTeam.teamKey))})`
    : 'Unavailable';
  const challenger = snapshot.nearestChallenger
    ? `${snapshot.nearestChallenger.shortName} (${formatPercent(top4Probability(payload, snapshot.nearestChallenger.teamKey))})`
    : 'Unavailable';
  const date = formatGeneratedDate(payload.metadata.generated_at);

  return {
    instagram: `IPL Top 4 Qualification Probabilities - ${date}\n\nCurrent Top 4: ${topFour}\nCutline: ${cutline}\nNearest challenger: ${challenger}\n\nProbabilities exclude NRR simulation.\n#IPL2026 #IPLPlayoffs`,
    x: `IPL Top 4 chances today: ${topFour}. Cutline: ${cutline}. Nearest challenger: ${challenger}. Updated ${date}. Probabilities exclude NRR simulation.`,
    whatsapp: `IPL Playoff Pulse (${date})\nTop 4: ${topFour}\nCutline: ${cutline}\nNearest challenger: ${challenger}\nProbabilities exclude NRR simulation.`,
  };
}

export async function copyToClipboard(text: string) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const element = document.createElement('textarea');
    element.value = text;
    document.body.appendChild(element);
    element.select();
    document.execCommand('copy');
    document.body.removeChild(element);
  }
}

export function raceCaption(payload: IplSeasonPayload) {
  const ordered = [...payload.standings].sort(rankingSort);
  const topFour = ordered.slice(0, 4).map((team) => team.shortName).join(', ');
  const chase = ordered.slice(4, 7).map((team) => team.shortName).join(', ');

  return `IPL 2026 Top 4 race: ${topFour} hold the playoff line right now. ${chase} are chasing. Exact all-combinations model, NRR shown when available. #IPL2026 #IPLPlayoffs`;
}

export function drawRoundedRect(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
) {
  context.beginPath();
  context.moveTo(x + radius, y);
  context.lineTo(x + width - radius, y);
  context.quadraticCurveTo(x + width, y, x + width, y + radius);
  context.lineTo(x + width, y + height - radius);
  context.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  context.lineTo(x + radius, y + height);
  context.quadraticCurveTo(x, y + height, x, y + height - radius);
  context.lineTo(x, y + radius);
  context.quadraticCurveTo(x, y, x + radius, y);
  context.closePath();
}

export async function exportRacePng(payload: IplSeasonPayload) {
  const teams = [...payload.standings].sort(rankingSort);
  const canvas = document.createElement('canvas');
  const width = 1080;
  const height = 1350;
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d');
  if (!context) {
    throw new Error('Canvas export is unavailable in this browser.');
  }

  const background = context.createLinearGradient(0, 0, width, height);
  background.addColorStop(0, '#0b1020');
  background.addColorStop(0.5, '#182036');
  background.addColorStop(1, '#24151b');
  context.fillStyle = background;
  context.fillRect(0, 0, width, height);

  context.fillStyle = 'rgba(255,255,255,0.09)';
  drawRoundedRect(context, 54, 54, 972, 1242, 34);
  context.fill();
  context.strokeStyle = 'rgba(255,255,255,0.2)';
  context.lineWidth = 2;
  context.stroke();

  context.fillStyle = '#facc15';
  context.font = '800 32px Inter, Arial, sans-serif';
  context.fillText('IPL PLAYOFF PULSE', 94, 122);
  context.fillStyle = '#ffffff';
  context.font = '900 84px Inter, Arial, sans-serif';
  context.fillText('Top 4 Odds', 94, 220);

  const y = 300;
  teams.forEach((team, index) => {
    const probability = payload.analysis.overallProbabilities[team.teamKey]?.top4 ?? 0;
    const rowHeight = 70;
    const rowY = y + index * 78;

    context.fillStyle = index < 4 ? 'rgba(255,255,255,0.14)' : 'rgba(255,255,255,0.08)';
    drawRoundedRect(context, 94, rowY, 892, rowHeight, 20);
    context.fill();

    context.fillStyle = teamColor(team.teamKey);
    drawRoundedRect(context, 116, rowY + 18, 34, 34, 17);
    context.fill();

    context.fillStyle = '#ffffff';
    context.font = '900 30px Inter, Arial, sans-serif';
    context.fillText(String(team.rank), 176, rowY + 43);
    context.fillText(team.shortName, 234, rowY + 43);

    context.fillStyle = 'rgba(255,255,255,0.62)';
    context.font = '700 22px Inter, Arial, sans-serif';
    context.fillText(`${team.points} pts  ${formatNrr(team.nrr)}`, 350, rowY + 43);

    context.fillStyle = 'rgba(255,255,255,0.18)';
    drawRoundedRect(context, 620, rowY + 24, 220, 18, 9);
    context.fill();

    context.fillStyle = teamColor(team.teamKey);
    drawRoundedRect(context, 620, rowY + 24, Math.max(8, probability * 2.2), 18, 9);
    context.fill();

    context.fillStyle = '#ffffff';
    context.font = '900 30px Inter, Arial, sans-serif';
    context.fillText(formatPercent(probability), 858, rowY + 45);
  });

  context.fillStyle = 'rgba(255,255,255,0.58)';
  context.font = '600 22px Inter, Arial, sans-serif';
  context.fillText(formatGeneratedDate(payload.metadata.generated_at), 94, 1252);

  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((value) => {
      if (value) {
        resolve(value);
      } else {
        reject(new Error('Could not create PNG.'));
      }
    }, 'image/png');
  });

  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'ipl-playoff-pulse-top4-race.png';
  link.click();
  URL.revokeObjectURL(url);
}
