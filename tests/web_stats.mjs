// Prints the JS port's numbers for a chat file as JSON (used by test_web_parity.py).
import { readFileSync } from "node:fs";
import { parse } from "../site/js/parser.js";
import { compute } from "../site/js/stats.js";

const s = compute(parse(readFileSync(process.argv[2], "utf-8")));
console.log(JSON.stringify({
  total_messages: s.totalMessages, total_words: s.totalWords, active_days: s.activeDays,
  conversations: s.conversations, longest_streak: s.longestStreak.days, busiest_day: s.busiestDay.messages,
  heatmap: s.heatmap, top_words: s.topWords, top_emojis: s.topEmojis,
  people: s.people.map((p) => ({ name: p.name, messages: p.messages, words: p.words, media: p.media, deleted: p.deleted,
    emojis: p.emojis, laughs: p.laughs, questions: p.questions, starts: p.conversationStarts, night: p.nightMessages,
    replies: p.replySeconds.length, median_reply: p.medianReplyMinutes })),
  awards: s.awards.map((a) => [a.title, a.winner]),
}));
