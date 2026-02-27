import React from 'react';
import { Card, CardTitle } from '../../../components/ui/card';

function IndexMovementCard({ indices = [], loading = false }) {
  return (
    <Card
      className="w-full fin-card flex-shrink-0"
      style={{ backgroundColor: 'transparent', border: 'none', boxShadow: 'none' }}
    >
      <div className="flex flex-col sm:flex-row sm:items-center gap-2.5 p-0">
        <div className="flex flex-col gap-3 flex-shrink-0 w-full sm:w-[200px]">
          <CardTitle
            className="dashboard-title-font text-base font-semibold"
            style={{ color: 'var(--color-text-primary)', letterSpacing: '0.15px', lineHeight: '24px' }}
          >
            Index Movement
          </CardTitle>
          <p
            className="text-xs"
            style={{ color: 'var(--color-text-primary)', opacity: 0.65, letterSpacing: '0.4px', lineHeight: '16px' }}
          >
            Some summary words
          </p>
        </div>
        <div className="grid grid-cols-2 sm:flex gap-2.5 flex-1 min-w-0">
          {loading
            ? Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="flex-1 flex flex-col gap-2 p-4 rounded-lg min-w-0 animate-pulse"
                  style={{ backgroundColor: 'var(--color-bg-card)', border: '1px solid var(--color-border-default)' }}
                >
                  <div className="h-4 rounded bg-foreground/10" style={{ width: '60%' }} />
                  <div className="h-4 rounded bg-foreground/10" style={{ width: '80%' }} />
                  <div className="h-4 rounded bg-foreground/10" style={{ width: '50%' }} />
                </div>
              ))
            : indices.map((index, idx) => {
                const pos = index.isPositive;
                const ch = Number(index.change);
                const pct = Number(index.changePercent);
                const changeStr = (pos ? '+' : '') + ch.toFixed(2);
                const pctStr = (pos ? '+' : '') + pct.toFixed(2) + '%';
                return (
                  <div
                    key={index.symbol}
                    className="flex-1 flex flex-col gap-2 p-4 transition-all relative"
                    style={{
                      backgroundColor: 'var(--color-bg-card)',
                      border: '1px solid var(--color-border-default)',
                      borderRadius: '8px',
                      minWidth: '0',
                    }}
                  >
                    {idx > 0 && (
                      <div
                        className="hidden sm:block absolute left-0 top-1/2 -translate-y-1/2 -translate-x-[5px]"
                        style={{ width: '1px', height: '60px', backgroundColor: 'var(--color-border-muted)' }}
                      />
                    )}
                    <div className="flex flex-col gap-2">
                      <p
                        className="text-sm leading-tight truncate"
                        style={{ color: 'var(--color-text-primary)', fontSize: '14px', lineHeight: '18px' }}
                      >
                        {index.name}
                      </p>
                      <p
                        className="text-sm tabular-nums leading-none"
                        style={{ color: 'var(--color-text-primary)', opacity: 0.65, fontSize: '14px', lineHeight: '18px' }}
                      >
                        {Number(index.price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </p>
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className={`text-sm font-normal tabular-nums ${pos ? 'text-up' : 'text-down'}`} style={{ fontSize: '14px', lineHeight: '18px' }}>
                          {changeStr}
                        </p>
                        <p className={`text-sm font-normal tabular-nums ${pos ? 'text-up' : 'text-down'}`} style={{ fontSize: '14px', lineHeight: '18px' }}>
                          {pctStr}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
        </div>
      </div>
    </Card>
  );
}

export default IndexMovementCard;
