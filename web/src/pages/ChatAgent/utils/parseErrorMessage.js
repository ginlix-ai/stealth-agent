/**
 * Parses raw error message strings into structured, human-readable parts.
 *
 * Handles common patterns from LLM API errors like:
 * - "Error calling model 'gemini-3-pro-preview' (Bad Request): 400 Bad Request. {'message': '...', 'status': 'Bad Request'}"
 * - "Error calling model 'gpt-4' (RateLimitError): You exceeded your current quota..."
 * - Plain text error messages
 *
 * @param {string} raw - The raw error message string
 * @returns {{ title: string, detail: string|null, model: string|null, statusCode: number|null }}
 */
export function parseErrorMessage(raw) {
  if (!raw || typeof raw !== 'string') {
    return { title: 'An error occurred', detail: null, model: null, statusCode: null };
  }

  // Try to extract model name: Error calling model 'model-name'
  const modelMatch = raw.match(/Error calling model\s+'([^']+)'/);
  const model = modelMatch ? modelMatch[1] : null;

  // Try to extract status code: 400, 401, 403, 429, 500, etc.
  const codeMatch = raw.match(/\b([45]\d{2})\b/);
  const statusCode = codeMatch ? parseInt(codeMatch[1], 10) : null;

  // Try to extract a nested JSON error message from the raw string.
  // The backend often wraps JSON in Python dict repr: {'message': '{"error": {...}}', 'status': '...'}
  const nestedMessage = extractNestedErrorMessage(raw);

  if (nestedMessage) {
    // Build a clean title from the error type
    const errorType = extractErrorType(raw);
    const title = errorType || (statusCode ? `Error ${statusCode}` : 'Request failed');
    return { title, detail: nestedMessage, model, statusCode };
  }

  // For "Error calling model ..." pattern without nested JSON, clean up the message
  if (modelMatch) {
    // Extract the parenthesized error type: (Bad Request), (RateLimitError), etc.
    const typeMatch = raw.match(/Error calling model\s+'[^']+'\s+\(([^)]+)\)/);
    const errorType = typeMatch ? typeMatch[1] : null;

    // Get everything after the first colon as the detail
    const colonIdx = raw.indexOf(':');
    let detail = colonIdx !== -1 ? raw.slice(colonIdx + 1).trim() : null;

    // Clean up the detail - remove status code prefix like "400 Bad Request. "
    if (detail) {
      detail = detail.replace(/^\d{3}\s+[A-Za-z ]+\.\s*/, '');
      // Remove Python dict wrappers if present
      detail = detail.replace(/^\{.*\}$/s, '').trim() || detail;
    }

    const title = errorType || (statusCode ? `Error ${statusCode}` : 'Model error');
    return { title, detail: detail || null, model, statusCode };
  }

  // Rate limit pattern
  if (/rate.?limit|too many requests|quota/i.test(raw)) {
    return { title: 'Rate limit exceeded', detail: raw, model, statusCode: statusCode || 429 };
  }

  // Authentication pattern
  if (/auth|unauthorized|forbidden|api.?key/i.test(raw)) {
    return { title: 'Authentication error', detail: raw, model, statusCode: statusCode || 401 };
  }

  // Fallback: keep the raw message but cap length for the title
  if (raw.length > 100) {
    return { title: 'Something went wrong', detail: raw, model, statusCode };
  }

  return { title: raw, detail: null, model, statusCode };
}

/**
 * Attempts to extract a human-readable error message from nested JSON/dict strings.
 */
function extractNestedErrorMessage(raw) {
  // Try to find JSON-like structure: {"error": {"message": "..."}}
  // These may appear with literal \n or python dict notation
  const patterns = [
    // JSON "message" field inside "error" object
    /"message"\s*:\s*"([^"]+)"/,
    // Python-style 'message': 'text'
    /'message'\s*:\s*'([^']+)'/,
  ];

  for (const pattern of patterns) {
    const matches = [...raw.matchAll(new RegExp(pattern, 'g'))];
    if (matches.length > 0) {
      // Prefer the deepest/last match (most specific error message)
      // but skip generic ones like the wrapper message
      const candidates = matches.map(m => m[1]).filter(m =>
        m.length > 3 &&
        !m.includes('{') &&
        !/^\d{3}\s/.test(m)
      );
      if (candidates.length > 0) {
        return candidates[candidates.length - 1];
      }
    }
  }

  return null;
}

/**
 * Extracts the error type from the parenthesized section of the error message.
 */
function extractErrorType(raw) {
  const match = raw.match(/\(([^)]+)\)\s*:/);
  if (match) {
    // Convert camelCase/PascalCase to readable: "BadRequest" → "Bad Request"
    return match[1].replace(/([a-z])([A-Z])/g, '$1 $2');
  }
  return null;
}
