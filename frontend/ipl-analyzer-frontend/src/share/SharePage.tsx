import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, Check, Clipboard, Download } from 'lucide-react';
import '../App.css';
import './SharePage.css';
import PageHeader from '../components/PageHeader';
import { ErrorState, LoadingState } from '../components/PageState';
import SiteHeader from '../components/SiteHeader';
import { DEFAULT_LEAGUE_ID, isLeagueComplete, loadIplData, type IplSeasonPayload } from '../data/iplData';
import { HUB_ID, leagueHref, loadLeagueIndex, type LeagueIndex } from '../data/leagues';
import { loadReelsManifest, publicAssetUrl, type ReelsManifest, type ReelsSlide } from '../data/reelsManifest';
import { formatGeneratedAt, setTeamPalette } from '../lib/standings';
import { copyToClipboard, exportRacePng, raceCaption, shareTexts, type ShareKind } from './sharing';
import { samePageHref } from '../lib/ui';

type CopyTarget = ShareKind | 'caption';

const SHARE_LABELS: Record<ShareKind, string> = {
  instagram: 'Instagram caption',
  x: 'X short post',
  whatsapp: 'WhatsApp share text',
};

function SharePage() {
  const [payload, setPayload] = useState<IplSeasonPayload | null>(null);
  const [index, setIndex] = useState<LeagueIndex | null>(null);
  const [manifest, setManifest] = useState<ReelsManifest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [manifestError, setManifestError] = useState<string | null>(null);
  const [copied, setCopied] = useState<CopyTarget | null>(null);
  const [exporting, setExporting] = useState(false);
  const [toolError, setToolError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    document.title = 'Share Kit | Playoff Pulse';

    // Slides are for the newest IPL season.
    loadLeagueIndex()
      .then((loaded) => {
        if (active) {
          setIndex(loaded);
        }
        return loaded.ipl ?? (loaded.default !== HUB_ID ? loaded.default : DEFAULT_LEAGUE_ID);
      })
      .catch(() => DEFAULT_LEAGUE_ID)
      .then((leagueId) => loadIplData(fetch, leagueId))
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
      <>
        <SiteHeader index={index} />
        <ErrorState homeHref={import.meta.env.BASE_URL} message={error} title="Share kit could not load" />
      </>
    );
  }

  if (!payload) {
    return (
      <>
        <SiteHeader index={index} />
        <LoadingState />
      </>
    );
  }

  const leagueOver = isLeagueComplete(payload);
  const packSourceTime = Date.parse(manifest?.source?.dataGeneratedAt ?? '');
  const archivedPack = leagueOver || Boolean(manifest && (!Number.isFinite(packSourceTime) || packSourceTime !== Date.parse(payload.metadata.generated_at)));
  const texts = shareTexts(payload);

  const handleCopy = async (target: CopyTarget, text: string) => {
    setToolError(null);
    setCopied(null);
    try {
      await copyToClipboard(text);
      setCopied(target);
      window.setTimeout(() => setCopied(null), 1600);
    } catch {
      setToolError('The text could not be copied. Try again, or download a graphic below.');
    }
  };

  const handleExport = async () => {
    setExporting(true);
    setCopied(null);
    try {
      setToolError(null);
      await exportRacePng(payload);
    } catch {
      setToolError('The graphic could not be created. Try again, or use one of the slides below.');
    } finally {
      setExporting(false);
    }
  };

  return (
    <>
      <a className="skip-link" href={samePageHref('#main')}>
        Skip to content
      </a>
      <SiteHeader currentLabel="Share kit" index={index} />
      <main className="pulse-app share-page" data-testid="share-kit" id="main">
        <PageHeader
          crumb={`Cricket · IPL ${payload.metadata.season}`}
          strap={
            <>
              Post data updated {formatGeneratedAt(payload.metadata.generated_at)}. Slides have their own pack date below.{' '}
              <a className="share-return" href={leagueHref(payload.league?.id ?? index?.ipl ?? DEFAULT_LEAGUE_ID)}>
                <ArrowLeft size={14} aria-hidden="true" /> Back to standings
              </a>
            </>
          }
          title="Share Kit"
        />

        <section className={`reels-panel share-feature ${leagueOver ? 'share-archive' : ''}`} aria-labelledby="post-title">
          <div className="section-heading">
            <h2 id="post-title">{leagueOver ? 'Season archive' : 'Today’s Race'}</h2>
            <p>{leagueOver ? 'Post tools return when the next season starts' : 'Copy a ready-made post or download the race graphic'}</p>
          </div>

          {toolError && <p className="reels-warning" role="alert">{toolError}</p>}
          {copied && <p className="share-feedback" role="status">Copied. Your post text is ready.</p>}
          {leagueOver ? (
            <p className="reels-warning">
              The IPL {payload.metadata.season} league stage is over. These slides are from the last league-stage update and
              do not show the final table.
            </p>
          ) : (
            <div className="reels-toolbar">
              <div className="caption-actions" role="group" aria-label="Copy post text">
                <button onClick={() => handleCopy('caption', raceCaption(payload))} type="button">
                  {copied === 'caption' ? <Check size={16} aria-hidden="true" /> : <Clipboard size={16} aria-hidden="true" />}
                  {copied === 'caption' ? 'Copied' : 'Race caption'}
                </button>
                {(Object.keys(SHARE_LABELS) as ShareKind[]).map((kind) => (
                  <button key={kind} onClick={() => handleCopy(kind, texts[kind])} type="button">
                    {copied === kind ? <Check size={16} aria-hidden="true" /> : <Clipboard size={16} aria-hidden="true" />}
                    {SHARE_LABELS[kind]}
                  </button>
                ))}
                <button disabled={exporting} onClick={handleExport} type="button">
                  <Download size={16} aria-hidden="true" />
                  {exporting ? 'Making PNG' : 'Race PNG'}
                </button>
              </div>
            </div>
          )}
        </section>

        <section className="reels-panel" aria-labelledby="reels-title">
          <div className="section-heading">
            <h2 id="reels-title">Reels Slides</h2>
            <p>{archivedPack ? 'Archived league-stage graphics · the pack date is shown below' : 'The newest slide pack, ready to download'}</p>
          </div>
          {archivedPack && !leagueOver && <p className="reels-warning">These slides are from an earlier data update and do not show the current table. Check their archive date before sharing.</p>}
          <ReelsGallery error={manifestError} manifest={manifest} archived={archivedPack} />
        </section>
      </main>
      <footer className="pulse-footer"><span>Model estimates for fans, not betting advice.</span><span>Cricket graphics from the published league data. Sources and model notes are on the league page.</span></footer>
    </>
  );
}

const ReelsGallery = ({ error, manifest, archived }: { error: string | null; manifest: ReelsManifest | null; archived: boolean }) => {
  if (error) {
    return <p className="reels-state" role="status">Latest Reels manifest unavailable: {error}</p>;
  }

  if (!manifest) {
    return <p className="reels-state" role="status">Loading latest Reels pack…</p>;
  }

  return (
    <>
      <div className="reels-toolbar">
        <div>
          <span className="mini-label">{archived ? 'Archived pack' : 'Latest pack'}</span>
          <strong>{manifest.latestDate || 'Unavailable'}</strong>
          <small>
            {manifest.slides.length} slide{manifest.slides.length === 1 ? '' : 's'} · {manifest.imageWidth}×
            {manifest.imageHeight}
          </small>
        </div>
      </div>

      <div className="reels-gallery" data-testid="reels-gallery">
        {manifest.slides.map((slide, index) => (
          <ReelSlideCard index={index} key={slide.path} slide={slide} archiveDate={archived ? slide.date ?? manifest.latestDate ?? undefined : undefined} />
        ))}
      </div>

      {manifest.slides.length === 0 && <p className="reels-state">No slide PNGs were listed in the latest manifest.</p>}
      {manifest.warnings.length > 0 && (
        <p className="reels-warning">Pack note: {manifest.warnings.join(' ')}</p>
      )}
    </>
  );
};

const ReelSlideCard = ({ index, slide, archiveDate }: { index: number; slide: ReelsSlide; archiveDate?: string }) => {
  const href = publicAssetUrl(slide.path);
  const [failedPreview, setFailedPreview] = useState(false);
  const usePreview = Boolean(slide.previewPath) && !failedPreview;
  const preview = usePreview ? publicAssetUrl(slide.previewPath) : href;
  const image = useRef<HTMLImageElement>(null);
  const [nearViewport, setNearViewport] = useState(index === 0 || typeof IntersectionObserver === 'undefined');

  useEffect(() => {
    if (nearViewport || !image.current) return;
    // Native lazy loading fetches several tall slides ahead on fast connections.
    // A bounded margin gives the first visible graphic the available bandwidth.
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setNearViewport(true);
        observer.disconnect();
      }
    }, { rootMargin: '400px 0px' });
    observer.observe(image.current);
    return () => observer.disconnect();
  }, [nearViewport]);

  return (
    <article className="reel-slide-card">
      <a href={href} aria-label={`Open Reels slide ${index + 1}`}>
        <img
          ref={image}
          alt={`IPL Playoff Pulse Reels slide ${index + 1}`}
          decoding="async"
          fetchPriority={index === 0 ? 'high' : undefined}
          height={usePreview ? slide.previewHeight ?? slide.imageHeight : slide.imageHeight}
          loading={index === 0 ? 'eager' : 'lazy'}
          onError={usePreview ? () => setFailedPreview(true) : undefined}
          src={nearViewport ? preview : undefined}
          width={usePreview ? slide.previewWidth ?? slide.imageWidth : slide.imageWidth}
        />
      </a>
      {archiveDate && <p className="share-archive-date">Archive · {archiveDate}</p>}
      <div>
        <span>Slide {String(index + 1).padStart(2, '0')}</span>
        <a href={href} download={slide.downloadName}>
          <Download size={16} aria-hidden="true" />
          Download
        </a>
      </div>
    </article>
  );
};

export default SharePage;
