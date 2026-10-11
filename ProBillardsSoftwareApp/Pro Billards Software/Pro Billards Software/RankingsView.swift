//
//  RankingsView.swift
//  Pro Billards Software
//

import SwiftUI

// MARK: - Theme (matches web: slate-950, felt, slate-900/800)

private enum RankingsTheme {
    static let background = Color(red: 0.03, green: 0.04, blue: 0.06)   // slate-950
    static let textPrimary = Color(red: 0.98, green: 0.98, blue: 0.99)   // slate-50
    static let textMuted = Color(red: 0.55, green: 0.58, blue: 0.63)     // slate-400
    static let felt = Color(hue: 0.39, saturation: 0.45, brightness: 0.32)  // --felt dark
    static let cardGradientStart = Color(red: 0.07, green: 0.08, blue: 0.11) // slate-900
    static let cardGradientEnd = Color(red: 0.09, green: 0.10, blue: 0.13)   // slate-800
    static let buttonBg = Color(red: 0.22, green: 0.24, blue: 0.27).opacity(0.8)   // slate-700/50
    static let buttonBorder = Color(red: 0.15, green: 0.17, blue: 0.19)            // slate-500/50
    static let rowFeltTint = Color(hue: 0.39, saturation: 0.45, brightness: 0.32).opacity(0.05)
}

struct RankingsView: View {
    enum ViewMode {
        case menu
        case table(system: String, title: String)
    }

    @State private var viewMode: ViewMode = .menu
    @State private var navStack: [String] = ["top"]
    @State private var rankings: [RankingItem] = []
    @State private var total: Int = 0
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var searchQuery: String = ""

    private var currentMenuItems: [RankingsMenuItem] {
        let level = navStack.last ?? "top"
        if level == "top" { return rankingsTopLevel }
        return rankingsMenuItems(for: level)
    }

    private var filteredRankings: [RankingItem] {
        guard !searchQuery.trimmingCharacters(in: .whitespaces).isEmpty else { return rankings }
        let q = searchQuery.lowercased()
        return rankings.filter {
            $0.player_name.lowercased().contains(q) ||
            (($0.country ?? "").lowercased().contains(q))
        }
    }

    var body: some View {
        NavigationStack {
            Group {
                switch viewMode {
                case .menu:
                    rankingsMenuView
                case .table(let system, let title):
                    rankingsTableView(system: system, title: title)
                }
            }
            .background(RankingsTheme.background)
            .foregroundStyle(RankingsTheme.textPrimary)
            .navigationTitle("Rankings")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
        }
    }

    // MARK: - Menu (drill-down)

    private var rankingsMenuView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                // Card section (matches web: rounded-2xl border-2 border-felt/30 gradient)
                VStack(alignment: .leading, spacing: 16) {
                    if navStack.count > 1 {
                        Button {
                            navStack.removeLast()
                        } label: {
                            HStack(spacing: 8) {
                                Image(systemName: "chevron.left")
                                    .font(.system(size: 18, weight: .semibold))
                                Text("Back")
                            }
                            .foregroundStyle(RankingsTheme.textPrimary)
                            .frame(minHeight: 44)
                            .padding(.horizontal, 16)
                            .padding(.vertical, 10)
                            .background(RankingsTheme.buttonBg)
                            .overlay(RoundedRectangle(cornerRadius: 12).stroke(RankingsTheme.buttonBorder, lineWidth: 1))
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                        }
                        .buttonStyle(.plain)
                    }

                    Text(navStack.last == "top" ? "🏆 Choose category" : "🏆 Choose ranking")
                        .font(.system(size: 22, weight: .bold))
                        .foregroundStyle(RankingsTheme.textPrimary)

                    LazyVStack(alignment: .leading, spacing: 10) {
                        ForEach(Array(currentMenuItems.enumerated()), id: \.offset) { _, item in
                            MenuOptionButton(item: item) {
                                handleMenuTap(item)
                            }
                        }
                    }
                }
                .padding(20)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(
                    LinearGradient(
                        colors: [RankingsTheme.cardGradientStart, RankingsTheme.cardGradientEnd],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .overlay(RoundedRectangle(cornerRadius: 16).stroke(RankingsTheme.felt.opacity(0.3), lineWidth: 2))
                .clipShape(RoundedRectangle(cornerRadius: 16))
                .shadow(color: .black.opacity(0.3), radius: 8, x: 0, y: 4)
            }
            .padding()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func handleMenuTap(_ item: RankingsMenuItem) {
        switch item {
        case .drill(let id, _, _):
            navStack.append(id)
        case .leaf(let system, let label, _):
            viewMode = .table(system: system, title: label)
            searchQuery = ""
            loadRankings(system: system)
        }
    }

    // MARK: - Table (ranking list)

    private func rankingsTableView(system: String, title: String) -> some View {
        VStack(spacing: 0) {
            // Back + hero card (matches web header)
            VStack(alignment: .leading, spacing: 12) {
                Button {
                    viewMode = .menu
                    rankings = []
                    errorMessage = nil
                    searchQuery = ""
                } label: {
                    HStack(spacing: 8) {
                        Image(systemName: "chevron.left")
                            .font(.system(size: 18, weight: .semibold))
                        Text("Back")
                    }
                    .foregroundStyle(RankingsTheme.textPrimary)
                    .frame(minHeight: 44)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(RankingsTheme.buttonBg)
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(RankingsTheme.buttonBorder, lineWidth: 1))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .buttonStyle(.plain)

                if !isLoading && errorMessage == nil && !rankings.isEmpty {
                    // Hero block: title + player count
                    VStack(alignment: .leading, spacing: 6) {
                        HStack(spacing: 8) {
                            Text("🏆")
                                .font(.title2)
                            Text("\(title) Tournament Rankings")
                                .font(.system(size: 20, weight: .bold))
                                .foregroundStyle(RankingsTheme.textPrimary)
                        }
                        Text("Professional Billiards Champion")
                            .font(.subheadline)
                            .fontWeight(.semibold)
                            .foregroundStyle(RankingsTheme.felt)
                        Text("\(total) professional players")
                            .font(.caption)
                            .foregroundStyle(RankingsTheme.textMuted)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .padding(.horizontal)
            .padding(.vertical, 12)

            if isLoading {
                VStack(spacing: 12) {
                    ProgressView()
                        .tint(RankingsTheme.textPrimary)
                    Text("Loading rankings…")
                        .font(.subheadline)
                        .foregroundStyle(RankingsTheme.textMuted)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let msg = errorMessage {
                VStack(spacing: 12) {
                    Text(msg)
                        .font(.subheadline)
                        .foregroundStyle(.red)
                        .multilineTextAlignment(.center)
                    Button("Retry") { loadRankings(system: system) }
                        .buttonStyle(.borderedProminent)
                        .tint(RankingsTheme.felt)
                }
                .padding()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if rankings.isEmpty {
                VStack(spacing: 12) {
                    Text("No rankings yet")
                        .font(.headline)
                    Text("Rankings will appear here once data is loaded.")
                        .font(.subheadline)
                        .foregroundStyle(RankingsTheme.textMuted)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                // Search bar (matches web)
                TextField("Search by player name or country...", text: $searchQuery)
                    .padding(12)
                    .background(RankingsTheme.cardGradientEnd)
                    .foregroundStyle(RankingsTheme.textPrimary)
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(RankingsTheme.buttonBorder, lineWidth: 1))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                    .padding(.horizontal)
                    .padding(.bottom, 8)
                    .autocorrectionDisabled()

                // Card-wrapped list
                List {
                    ForEach(Array(filteredRankings.enumerated()), id: \.offset) { _, item in
                        RankingRowView(item: item)
                    }
                }
                .listStyle(.plain)
                .scrollContentBackground(.hidden)
                .background(RankingsTheme.cardGradientEnd.opacity(0.5))
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(RankingsTheme.buttonBorder.opacity(0.5), lineWidth: 1))
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .padding(.horizontal)
                .refreshable { await loadRankingsAsync(system: system) }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func loadRankings(system: String) {
        errorMessage = nil
        isLoading = true
        Task { await loadRankingsAsync(system: system) }
    }

    private func loadRankingsAsync(system: String) async {
        do {
            let response = try await APIClient.fetchRankings(system: system, limit: 500, offset: 0)
            await MainActor.run {
                rankings = response.rankings
                total = response.total
                isLoading = false
            }
        } catch {
            await MainActor.run {
                errorMessage = error.localizedDescription
                isLoading = false
            }
        }
    }
}

// MARK: - Menu option button (matches web: dark slate, felt border, white text, shadow)

struct MenuOptionButton: View {
    let item: RankingsMenuItem
    let action: () -> Void

    private var borderColor: Color {
        switch itemStyle {
        case .heyball: return Color.purple.opacity(0.4)
        case .wpa, .wpba: return RankingsTheme.felt.opacity(0.3)
        }
    }

    private var itemStyle: MenuStyle {
        switch item {
        case .drill(_, _, let s): return s
        case .leaf(_, _, let s): return s
        }
    }

    private var label: String {
        switch item {
        case .drill(_, let l, _): return l
        case .leaf(_, let l, _): return l
        }
    }

    var body: some View {
        Button(action: action) {
            Text(label)
                .font(.system(size: 16, weight: .bold))
                .foregroundStyle(RankingsTheme.textPrimary)
                .multilineTextAlignment(.leading)
                .frame(maxWidth: .infinity, alignment: .leading)
                .frame(minHeight: 48)
                .padding(.vertical, 14)
                .padding(.horizontal, 16)
                .background(RankingsTheme.buttonBg)
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(borderColor, lineWidth: 2))
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .shadow(color: .black.opacity(0.25), radius: 4, x: 0, y: 2)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Row (felt tint for top 3, 2-decimal points, matches web mobile card)

struct RankingRowView: View {
    let item: RankingItem

    private var isFeatured: Bool { item.rank <= 3 }

    private var medalEmoji: String? {
        switch item.rank {
        case 1: return "🥇"
        case 2: return "🥈"
        case 3: return "🥉"
        default: return nil
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .top, spacing: 12) {
                HStack(spacing: 4) {
                    Text("\(item.rank)")
                        .font(.system(size: 22, weight: .bold))
                        .foregroundStyle(isFeatured ? RankingsTheme.felt : RankingsTheme.textMuted)
                    if let emoji = medalEmoji {
                        Text(emoji)
                            .font(.title2)
                    }
                }
                .frame(width: 44, alignment: .leading)

                VStack(alignment: .leading, spacing: 2) {
                    Text(item.player_name)
                        .font(isFeatured ? .headline : .body)
                        .fontWeight(isFeatured ? .semibold : .regular)
                        .foregroundStyle(RankingsTheme.textPrimary)
                    Text(item.country ?? "—")
                        .font(.subheadline)
                        .foregroundStyle(RankingsTheme.textMuted)
                }
                Spacer(minLength: 8)
            }

            HStack(alignment: .center, spacing: 8) {
                if let date = item.date, !date.isEmpty {
                    Text(date)
                        .font(.caption)
                        .foregroundStyle(RankingsTheme.textMuted)
                }
                if let lic = item.license_number, !lic.isEmpty {
                    Text(lic)
                        .font(.caption)
                        .foregroundStyle(RankingsTheme.textMuted)
                }
                if let stops = item.stops_played, stops > 0 {
                    Text("Stops: \(stops)")
                        .font(.caption)
                        .foregroundStyle(RankingsTheme.textMuted)
                }
                if let fargo = item.fargo_rating, fargo > 0 {
                    Text("Fargo: \(Int(fargo))")
                        .font(.caption)
                        .foregroundStyle(RankingsTheme.textMuted)
                }
                Spacer(minLength: 8)
                if let pts = item.points {
                    Text(String(format: "%.2f", pts))
                        .font(.system(.body, design: .monospaced))
                        .fontWeight(isFeatured ? .bold : .regular)
                        .foregroundStyle(RankingsTheme.textPrimary)
                    Text("pts")
                        .font(.caption)
                        .foregroundStyle(RankingsTheme.textMuted)
                }
            }
        }
        .padding(.vertical, 16)
        .padding(.horizontal, 4)
        .listRowBackground(isFeatured ? RankingsTheme.rowFeltTint : Color.clear)
        .listRowInsets(EdgeInsets(top: 0, leading: 16, bottom: 0, trailing: 16))
    }
}
