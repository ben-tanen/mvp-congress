
#--------------------#
# set up environment #
#--------------------#

rm(list = ls())

library(tidyverse)
library(tidylog)
library(glue)
library(httr)
library(stringr)

base_path <- "~/Desktop/Projects/mvp-congress"
data_path <- glue("{base_path}/data")

#---------------------#
# import scraped data #
#---------------------#

session <- 116

# import all hr bills
hr_bills <- lapply(list.files(data_path, pattern = glue("^hr{session}_bills.*[.]csv")), 
                   function(f) {
  read.csv(glue("{data_path}/{f}"))
}) %>% data.table::rbindlist() %>%
  set_names(gsub("X_", "", names(.))) %>%
  as_tibble() %>%
  mutate(bill_id = glue("{type}{id}-{session}"), .after = id)

# import all hr cosponsors
hr_cosponsors <- lapply(list.files(data_path, pattern = glue("^hr{session}_cosponsors.*[.]csv")),
                        function(f) {
  read.csv(glue("{data_path}/{f}"))
}) %>% data.table::rbindlist() %>%
  set_names(gsub("X_", "", names(.))) %>%
  as_tibble()

# import all s bills
s_bills <- lapply(list.files(data_path, pattern = glue("^s{session}_bills.*[.]csv")), 
                  function(f) {
  read.csv(glue("{data_path}/{f}"))
}) %>% data.table::rbindlist() %>%
  set_names(gsub("X_", "", names(.))) %>%
  as_tibble() %>%
  mutate(bill_id = glue("{type}{id}-{session}"), .after = id)

s_cosponsors <- lapply(list.files(data_path, pattern = glue("^s{session}_cosponsors.*[.]csv")),
                       function(f) {
  read.csv(glue("{data_path}/{f}"))
}) %>% data.table::rbindlist() %>%
  set_names(gsub("X_", "", names(.))) %>%
  as_tibble()

#--------------------#
# scrape hr district #
#--------------------#

api_key <- rjson::fromJSON(file = glue("{data_path}/api_keys.json"))$propublica_congress_key

hr_ids <- sort(unique(hr_cosponsors$cosponsor_id))

hr_roles <- lapply(hr_ids, function(id) {
  print(glue("id: {id}"))
  res <- GET(glue("https://api.propublica.org/congress/v1/members/{id}.json"), 
             add_headers("X-API-KEY" = api_key))
  districts <- lapply(content(res)$results[[1]]$roles, function(role) {
    if (role$short_title == "Rep.") {
      return(glue("Rep_{role$state}{role$district}_{role$congress}"))
    } else if (role$short_title == "Sen.") {
      return(glue("Sen_{role$state}_{role$congress}"))
    } else {
      return(glue("???_{role$congress}"))
    }
  }) %>% unlist() %>% paste0(collapse = "|")
})

hr_cw <- tibble(id = hr_ids,
                role = unlist(hr_roles)) %>%
  separate(role, sep = "[|]", 
           into = paste0("role", str_pad(1:25, 3, "left", "0"))) %>%
  pivot_longer(matches("role[0-9]+")) %>%
  filter(!is.na(value) & grepl(glue("_{session}$"), value)) %>%
  mutate(value = case_when(id == "G000582" ~ glue("Rep_PRAt-Large_{session}"),
                           id == "N000147" ~ glue("Rep_DCAt-Large_{session}"),
                           id == "P000610" ~ glue("Rep_VIAt-Large_{session}"),
                           id == "R000600" ~ glue("Rep_ASAt-Large_{session}"),
                           id == "S001177" ~ glue("Rep_MPAt-Large_{session}"),
                           id == "S001204" ~ glue("Rep_GUAt-Large_{session}"),
                           T ~ value)) %>%
  mutate(role = str_extract(value, "^(Rep|Sen)"),
         district = gsub("_", "", 
                         gsub("At-Large", "0", str_extract(value, "_[A-Z]{2}([0-9]+|At-Large)_")))) %>%
  filter(!is.na(role)) %>%
  distinct(id, role, district) %>%
  left_join(hr_cosponsors %>%
              distinct(id = cosponsor_id, name = cosponsor_name), 
            by = "id")

write.csv(hr_cw, glue("{data_path}/house_rep_cw_{session}.csv"), row.names = F)

#----------------------------------------------------#
# data checks: missing, duplicate, or failed queries #
#----------------------------------------------------#

# look for any bills not represented OR represented more than once
missing_or_dupe_bills.hr <- tibble(type = "hr",
       id = seq(1, max(hr_bills$id))) %>%
  left_join(hr_bills %>% count(id),
            by = "id") %>%
  filter(is.na(n) | n > 1)

missing_or_dupe_bills.s <- tibble(type = "s",
       id = seq(1, max(s_bills$id))) %>%
  left_join(s_bills %>% count(id),
            by = "id") %>%
  filter(is.na(n) | n > 1)

# look at query error bills
# NOTES: the following bills are missing for valid reasons
#   - hr10, 15, 16, 17, 18 were all reserved for speaker or minority leader
#   - hr9057 to 9067 were all introduced on 12/31/2020 and don't appear via API
#   - s5086 was introduced on 1/1/2021 and doesn't appear via API
failed_query_bills <- rbind(hr_bills, s_bills) %>%
  filter(status != "PARSED") %>%
  select(type, id)

#---------------------------------------------------#
# data checks: compare bill counts to other sources #
#---------------------------------------------------#

# calculate number of passed bills for each chamber
# compare to: https://www.govtrack.us/congress/bills/statistics
rbind(hr_bills, s_bills) %>%
  filter(status == "PARSED") %>%
  count(passed_house, passed_senate)

#----------------------------------------------------------------#
# data checks: compare consistency between bill + cosponsor data #
#----------------------------------------------------------------#

# compare number of cosponsors in cosponsor data to bill data
bills_w_too_few_cosponsors.hr <- rbind(hr_bills, s_bills) %>%
  select(bill_id, matches("cosponsor")) %>%
  left_join(hr_cosponsors %>% count(bill_id),
            by = "bill_id") %>%
  left_join(s_cosponsors %>% count(bill_id),
            by = "bill_id") %>%
  mutate(n = if_else(is.na(n.x), n.y, n.x)) %>%
  select(-n.x, -n.y) %>%
  filter(n < n_cosponsors)

#--------------------------------------------------------------#
# data checks: do we see every state + district as a cosponsor #
#--------------------------------------------------------------#

# calculate how many unique senators per state
senators_by_state <- s_cosponsors %>%
  group_by(cosponsor_state) %>%
  summarise(n = n_distinct(cosponsor_id),
            .groups = "drop")

# identify any states with an unusual number of senators
states_w_outlier_senators <- senators_by_state %>%
  filter(n < 2 | n > 3)

# calculate how many unique reps per district
reps_by_district <- hr_cosponsors %>%
  select(bill_id, cosponsor_id) %>%
  left_join(hr_cw, by = c("cosponsor_id" = "id")) %>%
  group_by(district) %>%
  summarise(n_cosponsors = n_distinct(cosponsor_id),
            n_bills = n(),
            .groups = "drop")

# identify any districts with an unusual number of reps
districts_w_outlier_cosponsors <- reps_by_district %>%
  filter(n_cosponsors > 2 | n_cosponsors < 1)

# check that we have the right number of districts represented
districts_per_state <- read.csv(glue("{data_path}/districts_per_state.csv"))

states_w_missing_districts <- reps_by_district %>%
  mutate(state_abbr = substr(district, 1, 2)) %>%
  count(state_abbr) %>%
  left_join(districts_per_state, by = "state_abbr") %>%
  filter(n != n_districts)

#--------------------#
# compile all checks #
#--------------------#

all_checks <- tibble(check = c("Any duplicate or missing bills, HR",
                               "Any duplicate or missing bills, S",
                               "Bill queries that failed",
                               "Bills with too few cosponsors",
                               "States with senator cosponsors",
                               "States with outlier number of cosponsoring senators",
                               "Districts with outlier number of cosponsoring representatives",
                               "States with missing districts"),
                     value = c(nrow(missing_or_dupe_bills.hr),
                               nrow(missing_or_dupe_bills.s),
                               nrow(failed_query_bills),
                               nrow(bills_w_too_few_cosponsors.hr),
                               nrow(senators_by_state),
                               nrow(states_w_outlier_senators),
                               nrow(districts_w_outlier_cosponsors),
                               nrow(states_w_missing_districts)),
                     expected = c(0, 0, 17, 0, 50, 0, 0, 0))

all_checks
