import { Input } from '../../../components/ui/input';
import { Search, Bell, HelpCircle, User, Mail } from 'lucide-react';
import UserConfigPanel from './UserConfigPanel';
import React, { useState, useEffect, useRef } from 'react';
import { getCurrentUser } from '../utils/api';

const DashboardHeader = () => {
  const [isUserPanelOpen, setIsUserPanelOpen] = useState(false);
  const [avatarUrl, setAvatarUrl] = useState(null);
  const [showHelpPopover, setShowHelpPopover] = useState(false);
  const helpRef = useRef(null);

  // Close popover on outside click
  useEffect(() => {
    if (!showHelpPopover) return;
    const handleClickOutside = (e) => {
      if (helpRef.current && !helpRef.current.contains(e.target)) {
        setShowHelpPopover(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showHelpPopover]);

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const data = await getCurrentUser();
        const url = data?.user?.avatar_url;
        const version = data?.user?.updated_at;
        setAvatarUrl(url ? `${url}?v=${version}` : null);
      } catch (err) {
        console.error('Failed to fetch user:', err);
      }
    };
    fetchUser();
  }, []);

  // Refresh avatar when panel closes (in case user uploaded new one)
  const handlePanelClose = () => {
    setIsUserPanelOpen(false);
    getCurrentUser().then(data => {
      const url = data?.user?.avatar_url;
      const version = data?.user?.updated_at;
      setAvatarUrl(url ? `${url}?v=${version}` : null);
    }).catch(() => {});
  };

  return (
    <>
      <div className="flex items-center justify-between px-5 py-2.5" style={{ backgroundColor: 'var(--color-bg-elevated)', borderBottom: '1px solid var(--color-border-muted)' }}>
        <h1 className="dashboard-title-font text-base font-medium" style={{ color: 'var(--color-text-primary)', letterSpacing: '0.15px' }}>Main Page</h1>
        <div className="flex items-center gap-4 flex-1 max-w-md mx-8">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5" style={{ color: 'var(--color-icon-muted)' }} />
            <Input 
              placeholder="Search" 
              className="pl-10 h-10 rounded-md text-sm"
              style={{ 
                backgroundColor: 'var(--color-bg-input)', 
                border: '0.5px solid var(--color-border-input)',
                color: 'var(--color-text-primary)',
                fontSize: '14px'
              }}
            />
          </div>
        </div>
        <div className="flex items-center gap-4">
          <Bell className="h-5 w-5 cursor-pointer transition-colors" style={{ color: 'var(--color-icon-muted)' }} />
          <div className="relative" ref={helpRef}>
            <HelpCircle
              className="h-5 w-5 cursor-pointer transition-colors"
              style={{ color: showHelpPopover ? 'var(--color-text-primary)' : 'var(--color-icon-muted)' }}
              onClick={() => setShowHelpPopover((prev) => !prev)}
            />
            {showHelpPopover && (
              <div
                className="absolute right-0 top-full mt-2 z-50 rounded-lg shadow-lg"
                style={{
                  backgroundColor: 'var(--color-bg-elevated)',
                  border: '1px solid var(--color-border-elevated)',
                  width: '280px',
                  padding: '16px',
                }}
              >
                <p
                  className="text-sm font-medium mb-3"
                  style={{ color: 'var(--color-text-primary)' }}
                >
                  If you have any questions or suggestions, please contact us through the following methods
                </p>
                <div
                  className="flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer transition-colors hover:opacity-80"
                  style={{ backgroundColor: 'var(--color-bg-input)' }}
                  onClick={() => {
                    window.location.href = 'mailto:support@ginlix.ai';
                    setShowHelpPopover(false);
                  }}
                >
                  <Mail className="h-4 w-4 flex-shrink-0" style={{ color: 'var(--color-accent-primary)' }} />
                  <div className="min-w-0">
                    <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>Email</p>
                    <p className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>support@test.ai</p>
                  </div>
                </div>
              </div>
            )}
          </div>
          <div 
            className="h-7 w-7 rounded-full flex items-center justify-center cursor-pointer transition-colors hover:bg-primary/30 overflow-hidden" 
            style={{ backgroundColor: 'var(--color-accent-soft)' }}
            onClick={() => setIsUserPanelOpen(true)}
          >
            {avatarUrl ? (
              <img src={avatarUrl} alt="avatar" className="h-full w-full object-cover" onError={() => setAvatarUrl(null)} />
            ) : (
              <User className="h-4 w-4" style={{ color: 'var(--color-accent-primary)' }} />
            )}
          </div>
        </div>
      </div>
      
      <UserConfigPanel
        isOpen={isUserPanelOpen}
        onClose={handlePanelClose}
      />
    </>
  );
};

export default DashboardHeader;
