import React from 'react';
import { Menu } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import { ScrollArea } from '../../../components/ui/scroll-area';

/**
 * Top Research list card. Data via props: items = [{ title, time }].
 */
function TopResearchCard({ items = [] }) {
  return (
    <Card className="fin-card flex flex-col h-full min-h-0 overflow-hidden">
      <CardHeader
        className="px-6 py-4 flex-shrink-0"
        style={{ borderBottom: '1px solid var(--color-border-muted)' }}
      >
        <div className="flex items-center justify-between">
          <CardTitle
            className="dashboard-title-font text-base font-semibold"
            style={{ color: 'var(--color-text-primary)', letterSpacing: '0.15px' }}
          >
            Top Research
          </CardTitle>
          <Menu
            className="h-4 w-4 cursor-pointer transition-colors"
            style={{ color: 'var(--color-text-primary)' }}
          />
        </div>
      </CardHeader>
      <CardContent
        className="px-6 pt-0 pb-0 flex-1 min-h-0 overflow-hidden"
        style={{ display: 'flex', flexDirection: 'column' }}
      >
        <ScrollArea className="w-full flex-1 min-h-0">
          <div className="space-y-0">
            {items.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center gap-2.5 py-2.5 cursor-pointer transition-colors"
                style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
              >
                <div
                  className="w-[90px] h-[54px] flex-shrink-0 rounded"
                  style={{ backgroundColor: 'var(--color-bg-chart-placeholder)' }}
                />
                <div className="flex-1 min-w-0">
                  <p
                    className="text-sm font-normal"
                    style={{ color: 'var(--color-text-primary)' }}
                  >
                    {item.title}
                  </p>
                </div>
                <p
                  className="text-sm font-normal text-right flex-shrink-0"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  {item.time}
                </p>
              </div>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

export default TopResearchCard;
