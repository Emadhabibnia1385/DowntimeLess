-- counting traffic between servers is on by default: switch it on for every server that exists now
UPDATE servers SET acct_on=1;
