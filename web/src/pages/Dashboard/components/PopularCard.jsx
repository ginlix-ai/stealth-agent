import React from 'react';
import { AlignEndHorizontal, Clock, Menu } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';

function PopularCard({ items = [] }) {
  return (
    <Card
      className="flex-shrink-0"
      style={{ background: 'var(--color-accent-gradient)', border: 'none', boxShadow: 'none', borderRadius: '4px' }}
    >
      <CardHeader className="px-5 py-4" style={{ paddingLeft: '20px', paddingRight: '24px', paddingTop: '16px', paddingBottom: '16px' }}>
        <div className="flex items-center justify-between">
          <CardTitle className="dashboard-title-font text-base font-semibold" style={{ color: 'var(--color-text-primary)', letterSpacing: '0.15px', lineHeight: '24px' }}>
            What's Popular
          </CardTitle>
          <Menu className="h-4 w-4 cursor-pointer transition-colors" style={{ color: 'var(--color-text-primary)' }} />
        </div>
      </CardHeader>
      <CardContent className="px-5 pt-0 pb-0" style={{ paddingLeft: '20px', paddingRight: '20px', paddingBottom: '20px' }}>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 w-full">
          {items.map((item, idx) => (
            <Card
              key={idx}
              className="w-full min-w-0 cursor-pointer transition-all"
              style={{ backgroundColor: 'var(--color-bg-card)', border: '1px solid var(--color-border-default)', borderRadius: '8px', boxSizing: 'border-box' }}
            >
              <CardContent className="p-3">
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="w-4 h-4 flex items-center justify-center flex-shrink-0">
                      <AlignEndHorizontal className="w-4 h-4" style={{ color: 'var(--color-text-primary)' }} />
                    </div>
                    <div className="flex items-center gap-2.5 flex-1 min-w-0">
                      <h3 className="font-semibold text-sm flex-1 min-w-0 truncate" style={{ color: 'var(--color-text-primary)', letterSpacing: '0.1px', lineHeight: '20px' }}>
                        {item.title}
                      </h3>
                      <svg className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--color-text-primary)', opacity: 0.65 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                  </div>
                  <div className="flex flex-col gap-2.5" style={{ paddingTop: '8px' }}>
                    <p className="text-xs line-clamp-2 min-w-0" style={{ color: 'var(--color-text-primary)', opacity: 0.65, letterSpacing: '0.4px', lineHeight: '16px' }}>
                      {item.description}
                    </p>
                    <div className="flex items-center gap-2" style={{ paddingTop: '8px' }}>
                      <div className="flex items-center gap-1 px-2 py-0.5 rounded-md flex-shrink-0" style={{ backgroundColor: 'var(--color-bg-tag)' }}>
                        <Clock className="w-3 h-3" style={{ color: 'var(--color-text-primary)', opacity: 0.65 }} />
                        <span className="text-xs" style={{ color: 'var(--color-text-primary)', opacity: 0.65 }}>{item.duration}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export default PopularCard;
