export const emailQueryKeys = {
  all: ["emails"],

  listPrefix: ["emails", "list"],
  list: (filters) => ["emails", "list", filters],

  mailboxes: ["emails", "mailboxes"],
  mailboxSummary: ["emails", "mailboxSummary"],

  mailboxMembersPrefix: ["emails", "mailboxMembers"],
  mailboxMembers: (mailboxUserSdwtProd) => ["emails", "mailboxMembers", mailboxUserSdwtProd],

  detailPrefix: ["emails", "detail"],
  detail: (emailId) => ["emails", "detail", emailId],

  htmlPrefix: ["emails", "html"],
  html: (emailId) => ["emails", "html", emailId],
}
