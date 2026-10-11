/**
 * Win Probability Calculations
 * 
 * Utilities for calculating match outcome probabilities based on player ratings
 */

/**
 * Calculate win probability based on Fargo ratings using ELO-style formula
 * 
 * Formula: P(player wins) = 1 / (1 + 10^((opponent_fargo - player_fargo) / 400))
 * 
 * @param playerFargo - Player's Fargo rating
 * @param opponentFargo - Opponent's Fargo rating
 * @returns Tuple of [player_win_prob, opponent_win_prob] or null if ratings unavailable
 */
export function calculateFargoWinProbability(
  playerFargo: number | null | undefined,
  opponentFargo: number | null | undefined
): [number, number] | null {
  if (
    playerFargo == null ||
    opponentFargo == null ||
    !Number.isFinite(playerFargo) ||
    !Number.isFinite(opponentFargo)
  ) {
    return null
  }

  const ratingDiff = opponentFargo - playerFargo
  const playerWinProb = 1.0 / (1.0 + Math.pow(10, ratingDiff / 400.0))
  const opponentWinProb = 1.0 - playerWinProb

  return [playerWinProb, opponentWinProb]
}

/**
 * Format win probability as percentage string
 * 
 * @param probability - Win probability (0.0 to 1.0)
 * @param decimals - Number of decimal places (default: 0)
 * @returns Formatted percentage string (e.g., "65%")
 */
export function formatWinProbability(probability: number, decimals = 0): string {
  const pct = (probability * 100).toFixed(decimals)
  return `${pct}%`
}

/**
 * Calculate win probability based on ALFa ratings
 * 
 * Similar to Fargo but may use different scaling factors
 * 
 * @param playerAlfa - Player's ALFa rating
 * @param opponentAlfa - Opponent's ALFa rating
 * @returns Tuple of [player_win_prob, opponent_win_prob] or null if ratings unavailable
 */
export function calculateAlfaWinProbability(
  playerAlfa: number | null | undefined,
  opponentAlfa: number | null | undefined
): [number, number] | null {
  if (
    playerAlfa == null ||
    opponentAlfa == null ||
    !Number.isFinite(playerAlfa) ||
    !Number.isFinite(opponentAlfa)
  ) {
    return null
  }

  // ALFa uses similar ELO-style calculation with rating difference scaled by 500
  const ratingDiff = playerAlfa - opponentAlfa
  const playerWinProb = 1.0 / (1.0 + Math.exp(-ratingDiff / 500.0))
  const opponentWinProb = 1.0 - playerWinProb

  return [playerWinProb, opponentWinProb]
}

/**
 * Get odds ratio from win probability
 * 
 * @param probability - Win probability (0.0 to 1.0)
 * @returns Odds ratio string (e.g., "2.5:1" for 0.714)
 */
export function probabilityToOdds(probability: number): string {
  if (probability <= 0 || probability >= 1) {
    return probability > 0.5 ? '∞:1' : '1:∞'
  }

  const odds = probability / (1 - probability)
  
  if (odds >= 1) {
    return `${odds.toFixed(1)}:1`
  } else {
    return `1:${(1 / odds).toFixed(1)}`
  }
}

/**
 * Get confidence level description for win probability
 * 
 * @param probability - Win probability (0.0 to 1.0)
 * @returns Description string (e.g., "High confidence", "Toss-up")
 */
export function getConfidenceLevel(probability: number): string {
  const absDiff = Math.abs(probability - 0.5)
  
  if (absDiff < 0.05) return 'Toss-up'
  if (absDiff < 0.15) return 'Slight edge'
  if (absDiff < 0.25) return 'Moderate advantage'
  if (absDiff < 0.35) return 'Strong favorite'
  return 'Heavy favorite'
}
