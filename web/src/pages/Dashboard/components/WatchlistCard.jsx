import React, { useState } from 'react';
import { MoreVertical, Plus, Trash2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../../components/ui/dialog';
import { Input } from '../../../components/ui/input';
import { ScrollArea } from '../../../components/ui/scroll-area';

/**
 * Watchlist panel: table + add modal. Data and handlers via props.
 * rows = [{ item_id?, symbol, price, change, changePercent, isPositive }]
 */
function WatchlistCard({
  rows = [],
  loading = false,
  addModalOpen = false,
  onAddModalClose,
  onHeaderAddClick,
  addSymbol = '',
  onAddSymbolChange,
  onAddSubmit,
  onDeleteItem,
}) {
  const [menuOpenId, setMenuOpenId] = useState(null);

  const handleDelete = (itemId) => {
    setMenuOpenId(null);
    onDeleteItem?.(itemId);
  };

  return (
    <Card className="panel flex flex-col flex-1 min-h-0">
      <CardHeader className="px-3 py-4 flex-shrink-0">
        <button type="button" onClick={onHeaderAddClick} className="flex items-center justify-between w-full text-left">
          <CardTitle className="dashboard-title-font text-base font-semibold" style={{ color: 'var(--color-text-primary)', letterSpacing: '0.15px' }}>
            Create watchlist
          </CardTitle>
          <Plus className="h-4 w-4 shrink-0" style={{ color: 'var(--color-text-primary)' }} />
        </button>
      </CardHeader>
      <CardContent className="px-2 pb-6 pt-0 flex-1 min-h-0">
        <ScrollArea className="h-full">
          <table className="w-full text-sm" style={{ tableLayout: 'fixed' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
                <th className="text-left py-2 px-2 font-normal text-xs" style={{ color: 'var(--color-text-secondary)', width: '26%' }}>Symbol</th>
                <th className="text-left py-2 px-2 font-normal text-xs" style={{ color: 'var(--color-text-secondary)', width: '24%' }}>Last Price</th>
                <th className="text-left py-2 px-2 font-normal text-xs" style={{ color: 'var(--color-text-secondary)', width: '24%' }}>Change</th>
                <th className="text-left py-2 px-2 font-normal text-xs" style={{ color: 'var(--color-text-secondary)', width: '24%' }}>% Change</th>
                <th className="w-8" style={{ width: '32px' }} />
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
                      <td colSpan={5} className="py-2.5 px-2">
                        <div className="h-4 w-3/4 rounded bg-white/10 animate-pulse" />
                      </td>
                    </tr>
                  ))
                : rows.map((item) => (
                    <tr key={item.item_id ?? item.symbol} className="transition-colors" style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
                      <td className="py-2.5 px-2 font-normal" style={{ color: 'var(--color-text-primary)' }}>{item.symbol}</td>
                      <td className="py-2.5 px-2 font-normal tabular-nums" style={{ color: 'var(--color-text-primary)' }}>
                        {Number(item.price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className="py-2.5 px-2 font-normal tabular-nums" style={{ color: item.isPositive ? 'var(--color-profit)' : 'var(--color-loss)' }}>
                        {(item.isPositive ? '+' : '') + Number(item.change).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className="py-2.5 px-2 font-normal tabular-nums" style={{ color: item.isPositive ? 'var(--color-profit)' : 'var(--color-loss)' }}>
                        {(item.isPositive ? '+' : '') + Number(item.changePercent).toFixed(2) + '%'}
                      </td>
                      <td className="py-2.5 px-2 relative">
                        {item.item_id ? (
                          <div className="relative inline-block">
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); setMenuOpenId((id) => (id === item.item_id ? null : item.item_id)); }}
                              className="p-1 rounded hover:opacity-80"
                              style={{ color: 'var(--color-text-secondary)' }}
                              aria-label="More options"
                            >
                              <MoreVertical className="h-4 w-4" />
                            </button>
                            {menuOpenId === item.item_id && (
                              <>
                                <div className="fixed inset-0 z-40" aria-hidden onClick={() => setMenuOpenId(null)} />
                                <div className="absolute right-0 top-full z-50 mt-0.5 min-w-[120px] rounded border py-1 shadow-lg" style={{ backgroundColor: 'var(--color-bg-elevated)', borderColor: 'var(--color-border-elevated)' }}>
                                  <button
                                    type="button"
                                    onClick={(e) => { e.stopPropagation(); handleDelete(String(item.item_id)); }}
                                    className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-white/10"
                                    style={{ color: 'var(--color-text-primary)' }}
                                  >
                                    <Trash2 className="h-3.5 w-3.5" style={{ color: 'var(--color-text-secondary)' }} />
                                    Delete
                                  </button>
                                </div>
                              </>
                            )}
                          </div>
                        ) : null}
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </ScrollArea>
      </CardContent>

      <Dialog open={addModalOpen} onOpenChange={(open) => !open && onAddModalClose?.()}>
        <DialogContent className="sm:max-w-sm text-white border" style={{ backgroundColor: 'var(--color-bg-elevated)', borderColor: 'var(--color-border-elevated)' }}>
          <DialogHeader>
            <DialogTitle className="dashboard-title-font" style={{ color: 'var(--color-text-primary)' }}>Add stock</DialogTitle>
          </DialogHeader>
          <div className="flex gap-2 pt-2" onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); onAddSubmit?.(); } }}>
            <Input
              placeholder="Symbol (e.g. AAPL)"
              value={addSymbol}
              onChange={(e) => onAddSymbolChange?.(e.target.value)}
              className="flex-1 text-white placeholder:text-gray-500 border"
              style={{ backgroundColor: 'var(--color-bg-card)', borderColor: 'var(--color-border-default)' }}
            />
            <button
              type="button"
              onClick={onAddSubmit}
              className="px-4 py-2 rounded font-medium shrink-0 hover:opacity-90"
              style={{ backgroundColor: 'var(--color-accent-primary)', color: 'var(--color-text-on-accent)' }}
            >
              Add
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

export default WatchlistCard;
