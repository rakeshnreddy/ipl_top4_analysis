import { useEffect, useState } from 'react';
import { AlertTriangle, ArrowLeft, Check, Clipboard, Download, Flame } from 'lucide-react';
import '../App.css';
import { isLeagueComplete, loadIplData, type IplSeasonPayload } from '../data/iplData';
import { loadReelsManifest, publicAssetUrl, type ReelsManifest, type ReelsSlide } from '../data/reelsManifest';
import { formatGeneratedAt, setTeamPalette } from '../lib/standings';
import { copyToClipboard, exportRacePng, raceCaption, shareTexts, type ShareKind } from './sharing';

type CopyTarget = ShareKind | 'caption';

const SHARE_LABELS: Record<ShareKind, string> = {
  instagram: 'Instagram caption',
  x: 'X short post',
  whatsapp: 'WhatsApp share text',
};

function SharePage() {
  const [payload, setPayload] = useState<IplSeasonPayload | null>(null);
  const [manifest, setManifest] = useState<ReelsManifest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [manifestError, setManifestError] = useState<string | null>(null);
  const [copied, setCopied] = useState<CopyTarget | null>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    let active = true;
    document.title = 'Share Kit | IPL Playoff Pulse';

    loadIplData()
      .then((data) => {
        if (active) {
          setTeamPalette(data.league?.teams);
          setPayload(data);
        }
      })
      .catch((fetchError: Error) => {
        if (active) {
          setError(fetchError.message);
        }
      });

    loadReelsManifest()
      .then((data) => {
        if (active) {
          setManifest(data);
        }
      })
      .catch((fetchError: Error) => {
        if (active) {
          setManifestError(fetchError.message);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  if (error) {
    return (
      <main className="pulse-app pulse-center">
        <section className="error-panel" role="alert">
          <AlertTriangle aria-hidden="true" />
          <h1>Share kit could not load</h1>
          <p>{error}</p>
        </section>
      </main>
    );
  }

  if (!payload) {
    return (
      <main className="pulse-app pulse-center">
        <div className="loading-panel" role="status" aria-live="polite">
          <Flame aria-hidden="true" />
          <span>Loading share kit...</span>
        </div>
      </main>
    );
  }

  const leagueOver = isLeagueComplete(payload);
  const texts = shareTexts(payload);

  const handleCopy = async (target: CopyTarget, text: string) => {
    await copyToClipboard(text);
    setCopied(target);
    window.setTimeout(() => setCopied(null), 1600);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      await exportRacePng(payload);
    } finally {
      setExporting(false);
    }
  };

  return (
    <main className="pulse-app" data-testid="share-kit">
      <section className="reels-panel" aria-labelledby="share-title">
        <div className="section-heading reels-heading">
          <div>
            <span className="panel-kicker">IPL Playoff Pulse</span>
            <h1 id="share-title">Share Kit</h1>
          </div>
          <a className="latest-pack-link" href={import.meta.env.BASE_URL}>
            <ArrowLeft size={12} aria-hidden="true" />
            Back to standings
          </a>
        </div>

        {leagueOver ? (
          <p className="reels-warning">
            The IPL {payload.metadata.season} league stage is over. These slides are from the last league-stage update and
            do not show the final table.
          </p>
        ) : (
          <div className="reels-toolbar">
            <div>
              <span className="mini-label">Post text</span>
              <strong>Today&apos;s race</strong>
              <small>Data updated {formatGeneratedAt(payload.metadata.generated_at)}</small>
            </div>
            <div className="caption-actions" aria-label="Copy post text">
              <button onClick={() => handleCopy('caption', raceCaption(payload))} type="button">
                {copied === 'caption' ? <Check size={13} aria-hidden="true" /> : <Clipboard size={13} aria-hidden="true" />}
                {copied === 'caption' ? 'Copied' : 'Race caption'}
              </button>
              {(Object.keys(SHARE_LABELS) as ShareKind[]).map((kind) => (
                <button key={kind} onClick={() => handleCopy(kind, texts[kind])} type="button">
                  {copied === kind ? <Check size={13} aria-hidden="true" /> : <Clipboard size={13} aria-hidden="true" />}
                  {SHARE_LABELS[kind]}
                </button>
              ))}
              <button disabled={exporting} onClick={handleExport} type="button">
                <Download size={13} aria-hidden="true" />
                {exporting ? 'Making PNG' : 'Race PNG'}
              </button>
            </div>
          </div>
        )}

        <ReelsGallery error={manifestError} manifest={manifest} />
      </section>
    </main>
  );
}

const ReelsGallery = ({ error, manifest }: { error: string | null; manifest: ReelsManifest | null }) => {
  if (error) {
    return <p className="reels-state" role="status">Latest Reels manifest unavailable: {error}</p>;
  }

  if (!manifest) {
    return <p className="reels-state" role="status">Loading latest Reels pack...</p>;
  }

  return (
    <>
      <div className="reels-toolbar">
        <div>
          <span className="mini-label">Latest Reels folder</span>
          <strong>{manifest.latestDate || 'Unavailable'}</strong>
          <small>
            {manifest.slides.length} slide{manifest.slides.length === 1 ? '' : 's'} · {manifest.imageWidth}×
            {manifest.imageHeight}
          </small>
        </div>
      </div>

      <div className="reels-gallery" data-testid="reels-gallery">
        {manifest.slides.map((slide, index) => (
          <ReelSlideCard index={index} key={slide.path} slide={slide} />
        ))}
      </div>

      {manifest.slides.length === 0 && <p className="reels-state">No slide PNGs were listed in the latest manifest.</p>}
      {manifest.warnings.length > 0 && (
        <p className="reels-warning">Pack note: {manifest.warnings.join(' ')}</p>
      )}
    </>
  );
};

const ReelSlideCard = ({ index, slide }: { index: number; slide: ReelsSlide }) => {
  const href = publicAssetUrl(slide.path);
  return (
    <article className="reel-slide-card">
      <a href={href} aria-label={`Open Reels slide ${index + 1}`}>
        <img
          alt={`IPL Playoff Pulse Reels slide ${index + 1}`}
          decoding="async"
          height={slide.imageHeight}
          loading="lazy"
          src={href}
          width={slide.imageWidth}
        />
      </a>
      <div>
        <span>Slide {String(index + 1).padStart(2, '0')}</span>
        <a href={href} download={slide.downloadName}>
          <Download size={13} aria-hidden="true" />
          Download
        </a>
      </div>
    </article>
  );
};

export default SharePage;
