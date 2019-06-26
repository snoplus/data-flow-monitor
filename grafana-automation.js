
/*
--Grafana Scraper--
By Jamie Rajewski <jrajewsk@ualberta.ca>
Changelog:
  - First build finalized on June 18, 2019

This script navigates through the login to Grafana and scrapes the efficiency
information
CURRENT RUNTIME: ~40 SECONDS
*/

'use strict';

const puppeteer = require('puppeteer');
const fs = require('fs');
// Load the config file here with CERN SSO credentials inside
const config = require('./grafana_config.json');

(async () => {
  try {
    // These arguments are REQUIRED to run without root due to there being no sandbox available
    const browser = await puppeteer.launch({args: ['--no-sandbox', '--disable-setuid-sandbox']});
    const [page] = await browser.pages();


    // Start at the grafana login page
    let target_URL = 'https://monit-grafana.cern.ch/login'
    await page.goto(target_URL);

    // --NOTE--
    // This button may DISAPPEAR; if it doesn't show up, assume the HTML element doesn't exist either so
    // fail at this stage
    // Now that were on the grafana login page, click on the 'Sign in with CERN SSO' button
    try {
      await Promise.all([
        page.click('[href="login/generic_oauth"]'),
        page.waitForNavigation( { 'waitUntil' : 'networkidle0' } ),
      ]);
    } catch (e){
      // Now write error to file
      var error = "error-The Sign in with CERN SSO button could not be located";
      fs.writeFile("data.json", error, (err) => {
        if (err) throw err;
      });
      console.log(error);
      await browser.close();
      process.exit(1);
    }

    // Insert a 4 second delay to ensure the page has had time to render (later delays are added for similar reasons)
    await page.waitFor(4000);

    // We are now at the CERN SSO page //

    // Click on the username field and enter it
    try {
      await page.waitForSelector('#ctl00_ctl00_NICEMasterPageBodyContent_SiteContentPlaceholder_txtFormsLogin');
    } catch (e){
      var error = "error-The username field selector isnt loaded";
      // Now write error to file
      fs.writeFile("data.json", error, (err) => {
        if (err) throw err;
      });
      console.log(error);
      await browser.close();
      process.exit(1);
    }
    
    await page.type('#ctl00_ctl00_NICEMasterPageBodyContent_SiteContentPlaceholder_txtFormsLogin', config.email);

    // Click on the password field and enter it
    await page.type('#ctl00_ctl00_NICEMasterPageBodyContent_SiteContentPlaceholder_txtFormsPassword', config.password);

    // Click the login button to be redirected to grafana dashboard
    try {
      await Promise.all([
        page.click('#ctl00_ctl00_NICEMasterPageBodyContent_SiteContentPlaceholder_btnFormsLogin'),
        page.waitForNavigation(),
      ]);
    } catch (e) {
      var error = "error-Timeout while waiting for grafana HOME to load";
      // Now write error to file
      fs.writeFile("data.json", error, (err) => {
        if (err) throw err;
      });
      console.log(error);
      await browser.close();
      process.exit(1);
    }

    await page.waitFor(4000);

    // Now that we've got an authenticated session on Grafana, go to the following URL which issues the
    // request for the raw data
    // **FOR REFERENCE**
    // This was found by loading the grafana dashboard, then looking at the network tab in the devtools to see what
    // requests were made , then manually inspecting them until the one that contained the data was found (in this case the one with 'efficiency'
    // was how I identified it)
    target_URL = 'https://monit-grafana.cern.ch/api/datasources/proxy/7794/query?db=monit_production_transfer&q=SELECT%20mean(%22efficiency%22)%20FROM%20%22one_month%22.%22transfer_fts_efficiency%22%20WHERE%20(%22vo%22%20%3D~%20%2F%5Esnoplus%5C.snolab%5C.ca%24%2F%20AND%20%22src_country%22%20%3D~%20%2F%5E.*%24%2F%20AND%20%22src_site%22%20%3D~%20%2F%5E.*%24%2F%20AND%20%22dst_country%22%20%3D~%20%2F%5E.*%24%2F%20AND%20%22dst_site%22%20%3D~%20%2F%5E.*%24%2F%20AND%20%22endpnt%22%20%3D~%20%2F%5E.*%24%2F)%20AND%20time%20%3E%3D%20now()%20-%2012h%20GROUP%20BY%20time(1h)%2C%20%22dst_hostname%22%20fill(none)&epoch=ms'
    try{
      await page.goto(target_URL);
    } catch(e) {
      var error = "error-Timeout while waiting for EFFICIENCY DATASOURCE to load";
      // Now write error to file
      fs.writeFile("data.json", error, (err) => {
        if (err) throw err;
      });
      console.log(error);
      await browser.close();
      process.exit(1);
    }

    await page.waitFor(4000);

    // Now that the page is loaded, extract the data
    try {
      await page.waitForSelector('pre');
    } catch (e) {
      var error = "error-Timeout while waiting for data elements to load in DATASOURCE";
      // Now write error to file
      fs.writeFile("data.json", error, (err) => {
        if (err) throw err;
      });
      console.log(error);
      await browser.close();
      process.exit(1);
    }

    const data_JSON = await page.$eval('pre', el => el.innerHTML);

    // Now write to file
    fs.writeFile("data.json", data_JSON, (err) => {
      if (err) throw err;
    });

    // Finally, clean up by closing the browser
    await browser.close();
  } catch (err) {
    console.error(err);
  }
})();
