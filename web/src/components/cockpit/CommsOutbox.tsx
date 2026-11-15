import { useState } from 'react';
import { CheckCircle2, Clock, Radio, Send, SignalZero, UserRoundCog } from 'lucide-react';
import type { Comms, CommsState, OutboxPacket } from '../../lib/types';
import { useWorkstation } from '../../state/WorkstationProvider';
import { compactHash, num } from '../../lib/format';
import { Badge, Button, Card } from '../ui';
import { cn } from '../../lib/utils';

const FLOW: CommsState[] = ['QUEUED_BLACKOUT', 'IN_TRANSIT', 'DELIVERED', 'ACKNOWLEDGED'];

const STATE_META: Record<CommsState, { label: string; tone: 'neutral' | 'watch' | 'nominal' | 'critical' }> = {
  QUEUED_BLACKOUT: { label: 'QUEUED · BLACKOUT', tone: 'neutral' },
  IN_TRANSIT: { label: 'IN TRANSIT', tone: 'watch' },
  DELIVERED: { label: 'DELIVERED', tone: 'nominal' },
  ACKNOWLEDGED: { label: 'ACKNOWLEDGED', tone: 'nominal' },
};

export function CommsOutbox({ comms }: { comms: Comms }) {
  const { busy, acknowledge } = useWorkstation();
  const [openPacket, setOpenPacket] = useState<string | null>(null);
  const [directive, setDirective] = useState('');
  const [sent, setSent] = useState<string | null>(null);
  // Explicit, visible demo role switch. The API only lets `flight-surgeon` acknowledge;
  // the cockpit must not silently spoof that header behind a crew-labelled button.
  const [actAsSurgeon, setActAsSurgeon] = useState(false);

  const submit = async (packet: OutboxPacket): Promise<void> => {
    const ok = await acknowledge(packet, directive, actAsSurgeon ? 'flight-surgeon' : undefined);
    if (ok) {
      setSent(packet.packet_id);
      setDirective('');
      setOpenPacket(null);
    }
  };

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-3">
        <div>
          <span className="label-micro">Store-and-forward outbox</span>
          <p className="mt-0.5 text-2xs text-ink-subtle">
            {comms.profile.label} · <span className="num">{num(comms.profile.delay_s, 1)} s</span> demo delay
          </p>
        </div>
        <Badge tone={comms.blackout ? 'neutral' : 'nominal'}>
          {comms.blackout ? <><SignalZero size={11} aria-hidden /> BLACKOUT</> : <><Radio size={11} aria-hidden /> LINK UP</>}
        </Badge>
      </div>

      <p className="border-b border-line bg-page px-4 py-2 text-2xs leading-4 text-ink-label">
        {comms.profile.real_world_note}
      </p>

      {comms.packets.length === 0 ? (
        <p className="px-4 py-5 text-center text-xs text-ink-subtle">
          No escalation packets. A packet is created only when the lifecycle reaches S4.
        </p>
      ) : (
        <ul className="divide-y divide-line">
          {[...comms.packets].reverse().map((packet) => {
            const meta = STATE_META[packet.comms_state];
            const index = FLOW.indexOf(packet.comms_state);
            const expanded = openPacket === packet.packet_id;
            return (
              <li key={packet.packet_id} className="px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="num text-2xs font-semibold text-ink">{packet.packet_id}</span>
                  <Badge tone={meta.tone}>
                    {packet.comms_state === 'IN_TRANSIT' ? <Clock size={11} aria-hidden /> : null}
                    {packet.comms_state === 'ACKNOWLEDGED' ? <CheckCircle2 size={11} aria-hidden /> : null}
                    {meta.label}
                    {packet.comms_state === 'IN_TRANSIT' && packet.countdown_s !== null
                      ? ` · ${num(packet.countdown_s, 1)} s` : ''}
                  </Badge>
                </div>

                <div className="mt-2 flex items-center gap-1" aria-label={`Packet ${packet.packet_id} transport progress`}>
                  {FLOW.map((stage, stageIndex) => (
                    <div key={stage} className="min-w-0 flex-1">
                      <div className={cn('h-1 rounded-full', stageIndex <= index ? 'bg-primary' : 'bg-neutral-soft')} />
                      <div className={cn('num mt-0.5 truncate text-2xs', stageIndex <= index ? 'text-ink-subtle' : 'text-ink-label')}>
                        {stage.split('_')[0]}
                      </div>
                    </div>
                  ))}
                </div>

                <p className="mt-2 text-xs leading-5 text-ink-body">{packet.sbar.situation}</p>

                <button
                  type="button"
                  className="mt-1.5 text-2xs font-medium text-primary-blue hover:underline"
                  aria-expanded={expanded}
                  aria-label={expanded ? 'Hide SBAR packet' : 'Read SBAR packet'}
                  onClick={() => setOpenPacket(expanded ? null : packet.packet_id)}
                >
                  {expanded ? 'Hide SBAR packet' : 'Read SBAR packet'}
                </button>

                {expanded ? (
                  <dl className="mt-2 space-y-1.5 rounded-lg border border-line bg-page px-3 py-2.5">
                    {(['situation', 'background', 'assessment', 'recommendation'] as const).map((field) => (
                      <div key={field}>
                        <dt className="label-micro">{field[0]?.toUpperCase()}{field.slice(1)}</dt>
                        <dd className="text-2xs leading-4 text-ink-body">{packet.sbar[field]}</dd>
                      </div>
                    ))}
                  </dl>
                ) : null}

                {packet.comms_state === 'DELIVERED' ? (
                  <div className="mt-2.5 rounded-lg border border-primary-blue/25 bg-primary-blue-soft px-3 py-2.5">
                    <label className="flex cursor-pointer items-start gap-2 text-2xs font-semibold text-ink">
                      <input
                        type="checkbox"
                        className="mt-0.5 h-3.5 w-3.5 rounded border-line-strong"
                        checked={actAsSurgeon}
                        onChange={(event) => setActAsSurgeon(event.target.checked)}
                      />
                      <span className="flex items-center gap-1.5">
                        <UserRoundCog size={13} aria-hidden /> Act as Flight Surgeon (demo role)
                      </span>
                    </label>
                    <label className="label-micro mt-2 block" htmlFor={`directive-${packet.packet_id}`}>
                      Acknowledge &amp; send directive
                    </label>
                    <textarea
                      id={`directive-${packet.packet_id}`}
                      className="mt-1.5 h-16 w-full rounded-md border border-line bg-white px-2 py-1.5 text-xs text-ink"
                      placeholder="Directive text for the acknowledgement receipt…"
                      value={directive}
                      onChange={(event) => setDirective(event.target.value)}
                    />
                    <Button size="sm" variant="blue" className="mt-1.5 w-full" busy={busy}
                            disabled={!actAsSurgeon || directive.trim().length === 0}
                            onClick={() => void submit(packet)}>
                      <Send size={12} aria-hidden /> Acknowledge &amp; send directive
                    </Button>
                    <p className="mt-1 text-2xs leading-4 text-ink-label">
                      Demo-grade role switch, not authentication. The receipt is hashed into the local
                      SHA-256 chain; no blockchain or EVM transaction exists.
                    </p>
                  </div>
                ) : null}

                {packet.receipt ? (
                  <div className="mt-2 rounded-lg border border-nominal/25 bg-nominal-soft px-3 py-2">
                    <div className="flex items-center gap-1.5 text-2xs font-semibold text-nominal-text">
                      <CheckCircle2 size={12} aria-hidden /> Receipt {packet.receipt.receipt_id}
                    </div>
                    <p className="mt-1 text-2xs leading-4 text-ink-body">{packet.receipt.directive}</p>
                    <p className="num mt-1 text-2xs text-ink-label">sha256 {compactHash(packet.receipt.sha256)}</p>
                  </div>
                ) : null}

                {sent === packet.packet_id && !packet.receipt ? (
                  <p className="mt-1.5 text-2xs text-nominal-text" role="status">Directive submitted.</p>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
